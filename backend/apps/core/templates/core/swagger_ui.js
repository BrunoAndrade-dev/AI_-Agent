// Read the current cookie on every request: login rotates the CSRF secret.
function currentCsrfRequest(request, ...args) {
  const headerName = "{{ csrf_header_name|escapejs }}";
  const cookieName = "{{ csrf_cookie_name|escapejs }}";
  const manualHeaders = new Headers(request.headers || {});
  const manualToken = manualHeaders.get(headerName);
  const result = requestInterceptor(request, ...args);
  const headers = new Headers(result.headers || {});
  // Headers are case-insensitive; remove both manual and automatic spellings.
  headers.delete(headerName);
  const target = new URL(result.url, window.location.href);
  const unsafe = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(
    (result.method || "GET").toUpperCase()
  );
  if (unsafe && target.origin === window.location.origin) {
    const cookie = document.cookie.split(";").map(value => value.trim())
      .find(value => value.startsWith(cookieName + "="));
    const token = cookie ? decodeURIComponent(cookie.slice(cookieName.length + 1)) : manualToken;
    if (token) headers.set(headerName, token);
  }
  result.headers = Object.fromEntries(headers.entries());
  return result;
}

{% include "drf_spectacular/swagger_ui.js" %}
