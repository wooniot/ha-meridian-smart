"""Meridian Automation Interface TCP client — poort 9014."""
import asyncio
import logging
import re
from typing import Callable, Optional

_LOGGER = logging.getLogger(__name__)

MERIDIAN_PORT = 9014
PING_INTERVAL = 60          # seconden tussen keepalive pings
RECONNECT_DELAY = 10        # seconden wachten na verbroken verbinding
CONNECT_TIMEOUT = 10        # seconden timeout bij verbinden


def _parse_fields(line: str) -> dict:
    """Parseer 'Key:"Value" Key2:"Value2"' naar een dict."""
    result = {}
    for match in re.finditer(r'(\w+):"([^"]*)"', line):
        result[match.group(1)] = match.group(2)
    return result


class MeridianState:
    """Houdt de actuele toestand van één Meridian zone bij."""

    def __init__(self):
        self.available: bool = False
        self.standby: bool = True
        self.volume: int = 0
        self.muted: bool = False
        self.source: str = ""
        self.source_number: int = -1
        self.sources: dict[int, str] = {}   # {0: "CD", 1: "Radio", ...}
        self.product: str = ""
        self.serial: str = ""
        self.zone_name: str = ""
        self.protocol_version: int = 1
        # Streaming (protocol v4)
        self.media_title: str = ""
        self.media_artist: str = ""
        self.media_album: str = ""
        self.media_image_url: str = ""
        self.player_state: str = ""   # "Play" / "Pause" / "Stop"


class MeridianClient:
    """
    Asyncio TCP client voor het Meridian Automation Interface protocol.

    - Verbindt op poort 9014
    - Stuurt ping elke 60s om verbinding levend te houden
    - Parseert unsolicited messages en roept callback aan bij statuswijziging
    """

    def __init__(self, host: str, state_callback: Optional[Callable] = None):
        self.host = host
        self.state = MeridianState()
        self._state_callback = state_callback
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._ping_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}

    # ------------------------------------------------------------------ #
    # Verbinding beheer                                                    #
    # ------------------------------------------------------------------ #

    async def connect(self) -> bool:
        """Verbind met het apparaat. Geeft True terug bij succes."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, MERIDIAN_PORT),
                timeout=CONNECT_TIMEOUT,
            )
            self._running = True
            self.state.available = True
            _LOGGER.info("Meridian verbonden: %s:%d", self.host, MERIDIAN_PORT)

            # Start luisterende taak en ping-taak
            self._listen_task = asyncio.create_task(self._listen_loop())
            self._ping_task = asyncio.create_task(self._ping_loop())

            # Haal initiële status op
            await self._initialize()
            return True

        except Exception as exc:
            _LOGGER.error("Meridian verbinding mislukt (%s): %s", self.host, exc)
            self.state.available = False
            return False

    async def disconnect(self):
        """Verbreek de verbinding netjes."""
        self._running = False
        if self._ping_task:
            self._ping_task.cancel()
        if self._listen_task:
            self._listen_task.cancel()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self.state.available = False

    async def start_persistent(self):
        """Houdt de verbinding permanent in stand — herverbindt na uitval."""
        while True:
            connected = await self.connect()
            if connected:
                # Wacht tot de listen-loop stopt (= verbinding verbroken)
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    if not self._running:
                        return
            _LOGGER.warning("Meridian verbinding verloren, herverbinden over %ds...", RECONNECT_DELAY)
            self.state.available = False
            self._notify()
            await asyncio.sleep(RECONNECT_DELAY)

    # ------------------------------------------------------------------ #
    # Commando's sturen                                                    #
    # ------------------------------------------------------------------ #

    async def send_command(self, cmd: str):
        """Stuur een '#' commando naar het apparaat."""
        await self._send(f"#{cmd}")

    async def query(self, q: str, timeout: float = 3.0) -> Optional[str]:
        """Stuur een '?' query en wacht op het antwoord."""
        fut = asyncio.get_event_loop().create_future()
        self._pending[q] = fut
        await self._send(f"?{q}")
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(q, None)
            _LOGGER.debug("Query timeout: %s", q)
            return None

    # --- Hoog-niveau commando's ---

    async def standby(self):
        await self.send_command("MSR SB")

    async def set_volume(self, volume: int):
        """Stel volume in (0–99)."""
        vol = max(0, min(99, int(volume)))
        await self.send_command(f"SVN {vol}")

    async def volume_up(self):
        await self.send_command("MSR VP")

    async def volume_down(self):
        await self.send_command("MSR VM")

    async def mute(self):
        await self.send_command("MSR MU")

    async def select_source(self, source_number: int):
        """Selecteer bron op nummer (0–11)."""
        await self.send_command(f"SRC {source_number}")

    async def select_source_by_name(self, name: str):
        """Selecteer bron op naam (bijv. 'CD')."""
        for num, legend in self.state.sources.items():
            if legend.lower() == name.lower():
                await self.select_source(num)
                return
        _LOGGER.warning("Bron niet gevonden: %s", name)

    async def media_play(self):
        await self.send_command("MSR PL")

    async def media_pause(self):
        await self.send_command("MSR PS")

    async def media_next(self):
        await self.send_command("MSR NX")

    async def media_previous(self):
        await self.send_command("MSR PV")

    # ------------------------------------------------------------------ #
    # Interne helpers                                                       #
    # ------------------------------------------------------------------ #

    async def _send(self, line: str):
        if not self._writer:
            return
        try:
            self._writer.write(f"{line}\n".encode())
            await self._writer.drain()
            _LOGGER.debug("→ %s", line)
        except Exception as exc:
            _LOGGER.error("Fout bij sturen '%s': %s", line, exc)

    async def _initialize(self):
        """Haal productstatus op na verbinding."""
        pid = await self.query("PID")
        if pid:
            self._handle_pid(pid)

        pgs = await self.query("PGS")
        if pgs:
            self._handle_pgs(pgs)

        gsl = await self.query("GSL")
        if gsl:
            self._handle_gsl(gsl)

        # Protocol v4: streaming info
        if self.state.protocol_version >= 4:
            gnp = await self.query("GNP")
            if gnp:
                self._handle_gnp(gnp)

        self._notify()

    async def _ping_loop(self):
        """Stuur elke minuut een ping om de verbinding levend te houden."""
        while self._running:
            await asyncio.sleep(PING_INTERVAL)
            await self._send("#PNG")

    async def _listen_loop(self):
        """Lees continu berichten van het apparaat."""
        try:
            while self._running:
                line = await self._reader.readline()
                if not line:
                    _LOGGER.warning("Meridian verbinding gesloten door apparaat")
                    break
                decoded = line.decode(errors="ignore").strip()
                if decoded:
                    _LOGGER.debug("← %s", decoded)
                    self._handle_line(decoded)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _LOGGER.error("Fout in listen loop: %s", exc)
        finally:
            self._running = False
            self.state.available = False

    def _handle_line(self, line: str):
        """Verwerk één binnenkomende regel."""
        if not line:
            return

        prefix = line[0]
        rest = line[1:].strip()

        if prefix == "*":
            # Antwoord op commando of query
            self._handle_reply(rest)

        elif prefix == "!":
            # Unsolicited status update van het apparaat
            self._handle_unsolicited(rest)

        # '#PNG' echo terug negeren

    def _handle_reply(self, rest: str):
        """Verwerk een '*' antwoord — los wachtende queries op."""
        # Format: "PGS Standby:... " of "ACK" of "NAK ..." of "ERR ..."
        parts = rest.split(None, 1)
        if not parts:
            return
        key = parts[0]
        data = parts[1] if len(parts) > 1 else ""

        if key == "ACK" or key == "NAK" or key == "ERR":
            return  # Wordt niet verder verwerkt

        # Ping antwoord
        if key == "PNG":
            return

        # Los wachtende query-future op
        if key in self._pending:
            fut = self._pending.pop(key)
            if not fut.done():
                fut.set_result(data)
            return

        # Verwerk als data-update (bijv. bij unsolicited die query-formaat heeft)
        self._dispatch_data(key, data)

    def _handle_unsolicited(self, rest: str):
        """Verwerk een '!' unsolicited bericht."""
        parts = rest.split(None, 1)
        if not parts:
            return
        msg_type = parts[0]
        data = parts[1] if len(parts) > 1 else ""
        self._dispatch_data(msg_type, data)

    def _dispatch_data(self, msg_type: str, data: str):
        """Stuur data naar de juiste handler op basis van berichttype."""
        changed = False

        if msg_type == "PID":
            self._handle_pid(data)
            changed = True
        elif msg_type == "SRC":
            self._handle_src(data)
            changed = True
        elif msg_type == "OFF":
            self.state.standby = True
            changed = True
        elif msg_type == "VMU":
            self._handle_vmu(data)
            changed = True
        elif msg_type == "PGS":
            self._handle_pgs(data)
            changed = True
        elif msg_type == "GSL":
            self._handle_gsl(data)
            changed = True
        elif msg_type == "NPC":
            self._handle_gnp(data)
            changed = True
        elif msg_type == "GNP":
            self._handle_gnp(data)
            changed = True
        elif msg_type == "PSC":
            self._handle_psc(data)
            changed = True
        elif msg_type == "ZNC":
            fields = _parse_fields(data)
            self.state.zone_name = fields.get("ZoneName", self.state.zone_name)
            changed = True
        elif msg_type in ("ARV",):
            _LOGGER.info("Meridian sluit verbinding: %s", data)

        if changed:
            self._notify()

    def _handle_pid(self, data: str):
        fields = _parse_fields(data)
        self.state.product = fields.get("Product", "")
        self.state.serial = fields.get("SerialNumber", "")
        self.state.zone_name = fields.get("ZoneName", "")
        try:
            self.state.protocol_version = int(fields.get("ProtocolVersion", "1"))
        except ValueError:
            self.state.protocol_version = 1

    def _handle_pgs(self, data: str):
        fields = _parse_fields(data)
        self.state.standby = fields.get("Standby", "On") == "Standby"
        try:
            self.state.source_number = int(fields.get("Source", "-1"))
        except ValueError:
            self.state.source_number = -1
        self.state.source = fields.get("Legend", "")
        self.state.muted = fields.get("Mute", "Demute") == "Mute"
        try:
            self.state.volume = int(fields.get("Volume", "0"))
        except ValueError:
            self.state.volume = 0

    def _handle_src(self, data: str):
        fields = _parse_fields(data)
        try:
            self.state.source_number = int(fields.get("Source", "-1"))
        except ValueError:
            self.state.source_number = -1
        self.state.source = fields.get("Legend", "")
        self.state.muted = fields.get("Mute", "Demute") == "Mute"
        try:
            self.state.volume = int(fields.get("Volume", str(self.state.volume)))
        except ValueError:
            pass
        self.state.standby = False

    def _handle_vmu(self, data: str):
        fields = _parse_fields(data)
        self.state.muted = fields.get("Mute", "Demute") == "Mute"
        try:
            self.state.volume = int(fields.get("Volume", str(self.state.volume)))
        except ValueError:
            pass

    def _handle_gsl(self, data: str):
        """Parseer bronnenlijst: Source:"0" Legend:"CD" Enabled:"Yes" ..."""
        self.state.sources = {}
        for match in re.finditer(r'Source:"(\d+)"\s+Legend:"([^"]*)"\s+Enabled:"(\w+)"', data):
            num = int(match.group(1))
            legend = match.group(2)
            enabled = match.group(3) == "Yes"
            if enabled:
                self.state.sources[num] = legend

    def _handle_gnp(self, data: str):
        fields = _parse_fields(data)
        self.state.media_title = fields.get("Track", "")
        self.state.media_album = fields.get("Album", "")
        self.state.media_artist = fields.get("Artist", "")
        self.state.media_image_url = fields.get("URL", "")

    def _handle_psc(self, data: str):
        fields = _parse_fields(data)
        self.state.player_state = fields.get("PlayerState", "")

    def _notify(self):
        """Roep de callback aan zodat HA de entity kan updaten."""
        if self._state_callback:
            self._state_callback()
