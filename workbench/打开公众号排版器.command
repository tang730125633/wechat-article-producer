#!/bin/zsh
set -e
cd "$(dirname "$0")"

if ! security find-generic-password -s "Tang WeChat Publisher" -a appid >/dev/null 2>&1 || \
   ! security find-generic-password -s "Tang WeChat Publisher" -a appsecret >/dev/null 2>&1; then
  echo "首次使用，请配置微信公众号接口。"
  python3 server.py configure
fi

port=8767
status="$(curl --noproxy '*' --connect-timeout 0.2 --max-time 0.5 -fsS "http://127.0.0.1:$port/api/wechat/status" 2>/dev/null || true)"

if print -r -- "$status" | python3 -c 'import json,sys; raise SystemExit(json.load(sys.stdin).get("app") != "wechat-article-producer-workbench-v2")' 2>/dev/null; then
  open "http://127.0.0.1:$port/"
  exit 0
fi

if [[ -n "$status" ]] || nc -z 127.0.0.1 "$port" 2>/dev/null; then
  echo "端口 $port 已被其他程序占用，请先关闭它再重试。"
  exit 1
fi

exec env WECHAT_WORKBENCH_PORT="$port" python3 server.py --open-browser
