#!/usr/bin/env bash
for host in 1.1.1.1 8.8.8.8 9.9.9.9; do
  ms=$(ping -c1 -W1 "$host" 2>/dev/null | sed -n 's/.*time=\([0-9.]*\).*/\1/p')
  [ -n "$ms" ] && break
done
if [ -z "$ms" ]; then
  echo '{"text":"● ---","class":"bad","tooltip":"Disconnected"}'
else
  ms=${ms%.*}
  cls=good; [ "$ms" -gt 80 ] && cls=mid; [ "$ms" -gt 200 ] && cls=bad
  echo "{\"text\":\"● ${ms}ms\",\"class\":\"$cls\",\"tooltip\":\"Ping: ${ms}ms\"}"
fi
