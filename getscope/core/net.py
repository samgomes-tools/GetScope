"""Acesso HTTP com a lista de certificados embutida (certifi): os caminhos do OpenSSL
mudam entre Arch, Debian e Fedora, e o AppImage precisa funcionar em todos."""
import ssl
import urllib.request

_CTX = None


def context():
    global _CTX
    if _CTX is None:
        _CTX = ssl.create_default_context()  # certificados do sistema (e SSL_CERT_FILE, se houver)
        try:
            import certifi
            _CTX.load_verify_locations(cafile=certifi.where())  # + lista embutida
        except Exception:  # noqa: BLE001
            pass
    return _CTX


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def urlopen(url, timeout=30, method=None, follow=True):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GetScope"}, method=method)
    handlers = [urllib.request.HTTPSHandler(context=context())]
    if not follow:
        handlers.append(_NoRedirect())
    return urllib.request.build_opener(*handlers).open(req, timeout=timeout)
