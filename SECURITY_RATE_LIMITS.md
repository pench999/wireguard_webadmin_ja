# MFA and Session Creation Rate Limits

## Defaults

- All OTP verification paths (enrollment, provisioning, VPN unlock) share one
  per-user failure budget: 5 failures per fixed 15-minute window.
- Successful OTP verification does not consume this budget or reset past failures.
- Both public session-creation POST endpoints share 30 requests per source IP per
  fixed minute and 300 requests globally per minute, including malformed requests.
- Rejected per-IP requests do not consume global capacity. Device IDs and browser
  cookies cannot reset these budgets. Concurrent in-flight OTP checks reserve slots.
- HTTP 429 includes Retry-After. A counter-storage failure denies processing with
  HTTP 503 instead of silently bypassing the limit.
- Counters use conditional atomic SQL increments, shared across workers/restarts.
  Expired rows are removed when new windows are created. Stored keys are HMACs,
  not plaintext IP addresses. No OTP, token, or configuration is stored in them.

Fixed windows are not rolling windows. A burst near a window boundary can reach
up to twice the single-window limit. Browser/client authentication sessions may
expire while waiting; start a fresh authentication request after the wait.
These controls do not replace login throttling, edge limits, or device revocation
revalidation. Status polling and other API families are outside this change.

## Nginx deployment

By default, X-Forwarded-For is ignored. Set SECURITY_TRUSTED_PROXY_CIDRS only to
the exact Nginx source address(es) as seen by Django, not to an arbitrary private
network or 0.0.0.0/0. Without this setting, users behind Nginx share its IP budget.

For a single public-facing Nginx proxy, its existing proxy location should include:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
```

If other trusted proxies precede Nginx, configure Nginx real_ip handling first.
Do not trust client-supplied forwarding headers. Restrict the backend port so only
Nginx and the necessary internal Docker services can access it.

Example .env values (the proxy address below is ONLY an example):

```dotenv
SECURITY_TRUSTED_PROXY_CIDRS=172.20.0.1/32
MFA_MAX_FAILURES=5
MFA_FAILURE_WINDOW_SECONDS=900
ANONYMOUS_API_IP_LIMIT=30
ANONYMOUS_API_GLOBAL_LIMIT=300
```

The supplied Compose files forward these variables. Preserve local fixed-IP and
wg_net customizations when merging changes. Verify the actual Nginx source address
before enabling trust. The backend walks forwarding addresses right-to-left and
stops at the first untrusted address.

Application limits still incur HTTP/DB work for rejected requests. Add Nginx
limit_req/connection/body-size limits to reject large floods before Django. Apply
strict session-creation limits only to `/api/client/v1/sessions/` and
`/api/client/v1/provisioning/`, not to the regular two-second status polling paths.
Choose capacity for expected shared-NAT traffic and monitor HTTP 429/503 responses.

Example edge configuration (adapt, do not replace your existing TLS/server config):

```nginx
# http context
limit_req_zone $binary_remote_addr zone=wgmfa_session_create:10m rate=30r/m;

# Existing server context. Match only session creation, not status polling.
location ~ ^/api/client/v1/(sessions|provisioning)/$ {
    limit_req zone=wgmfa_session_create burst=10 nodelay;
    limit_req_status 429;
    client_max_body_size 16k;
    error_page 429 = @wgmfa_rate_limited;
    # Replace with the SAME upstream as your current proxy configuration.
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache off;
    proxy_intercept_errors off;
}

location @wgmfa_rate_limited {
    default_type application/json;
    add_header Retry-After 60 always;
    add_header Cache-Control no-store always;
    return 429 '{"error":"too_many_sessions","retry_after":60}';
}
```

Inspect existing location precedence, headers and upstream before applying this
example; a `^~ /api/` prefix location can prevent the regex location from matching.
Run `sudo nginx -t` before reloading. Nginx uses a leaky-bucket rate rather than
the application's fixed windows. Reference: https://nginx.org/en/docs/http/ngx_http_limit_req_module.html

## Update and acceptance

This change REQUIRES user_manager migration 0013. Back up the DB before deploying.
The normal WebAdmin init script runs migrations before starting Gunicorn. If
using a custom startup, run `python manage.py migrate` explicitly.

Verify normal MFA setup, provisioning and connection; exhaust the failure budget
across different MFA paths and confirm valid codes are blocked until expiry;
verify other users remain unaffected. Test rotated device IDs, forged XFF headers,
separate clients behind the trusted proxy, HTTP 429 Retry-After, and worker restart
persistence. Do not perform flood tests against the live VPN service.
