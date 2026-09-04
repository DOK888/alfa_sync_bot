# Shadow Runtime Design

## Goal

Run the new SQLite foundation against the existing production JSON report without changing the running `alfa_sync_bot`, sending Telegram messages, changing Google Calendar, or writing into the legacy data directory.

## Data flow

The legacy bot remains the only writer of `alfa_data_parsed.json`. The new process receives its path as configuration, reads it once per cycle, normalizes recognised lesson fields into `LessonSnapshot`, and reconciles each school into a separate SQLite database. It writes only its own state directory and an aggregate status file.

`legacy:tetrika` and `legacy:wellkid` are independent sources. An import is complete only when the JSON has a mapping for that school and a list-valued `lessons` field. Missing or malformed sections create no deletion events.

The legacy report has no stable external lesson ID. The bridge uses a deterministic fallback key made from school, date, group and duration; moved lessons can therefore appear as a removal plus a new lesson. The later direct CRM adapter will replace this fallback with the CRM ID.

## Runtime modes

- `shadow` is the default mode. It performs import and prints/writes aggregate counts only. It has no Telegram dependency and no public port.
- `telegram` will be a separate later mode. It reads only the shadow SQLite schedule, never creates lessons, and is disabled by default.

## Deployment boundary

The shadow Compose service has a read-only bind mount to the legacy report directory and a separate writable `/state` directory. It does not mount `auth`, does not receive the production Telegram token, does not publish port `8123`, and does not use the legacy Compose project name or container name.

## Validation

Synthetic tests cover valid import, malformed/partial reports, idempotency, schedule interval loading, and aggregate output. Server validation is a one-shot import against a copy of the existing report, then repeated shadow imports without notifications. Production switch requires a separate approval after comparison.
