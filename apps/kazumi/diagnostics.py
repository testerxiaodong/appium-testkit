"""Extract observed HTTP outcomes, without guessing missing transport causes."""

import re

_http = re.compile(
    r"HTTP: <-- (?P<status>\S+) (?P<method>GET|POST|PUT|DELETE|PATCH) "
    r"(?P<url>\S+)(?: (?P<duration>\d+)ms)?"
)


def collect_kazumi_network(path):
    source = path / "app-log-excerpt.txt"
    if not source.exists():
        source = path / "ios-system.log"
    records = []
    if source.exists():
        for line in source.read_text(errors="replace").splitlines():
            match = _http.search(line)
            if match:
                record = match.groupdict()
                record["original_log_line"] = line
                records.append(record)
    return {
        "source": source.name,
        "requests": records,
        "scope": "Observed app log excerpt; may include earlier sessions. Correlate timestamps.",
        "limitation": "unknown is a recorded Dio category, not proof of DNS/TLS/proxy failure. "
        "Request bodies, server trace IDs and raw exceptions require app instrumentation.",
    }
