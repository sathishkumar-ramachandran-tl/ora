"""OAuth2 client registration (Google, Microsoft) via Authlib.

Registration is conditional on credentials being configured, so the app still boots
in local dev without OAuth set up — only /auth/oauth/<provider>/* routes require it.
"""
from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_oauth(app) -> None:
    oauth.init_app(app)

    if app.config.get('GOOGLE_OAUTH_CLIENT_ID'):
        oauth.register(
            name='google',
            client_id=app.config['GOOGLE_OAUTH_CLIENT_ID'],
            client_secret=app.config['GOOGLE_OAUTH_CLIENT_SECRET'],
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )

    if app.config.get('MICROSOFT_OAUTH_CLIENT_ID'):
        tenant = app.config.get('MICROSOFT_OAUTH_TENANT', 'common')
        oauth.register(
            name='microsoft',
            client_id=app.config['MICROSOFT_OAUTH_CLIENT_ID'],
            client_secret=app.config['MICROSOFT_OAUTH_CLIENT_SECRET'],
            server_metadata_url=f'https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
