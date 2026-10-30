"""Check Label Studio token type and authentication without printing credentials.
Insert a NEW token locally. Do not commit or share this file.
"""
import base64
import datetime
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

URL = 'https://label.momo-jojo.com'
PROJECT_ID = 9
API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6ODA5OTg1MTMxOSwiaWF0IjoxNzkyNjUxMzE5LCJqdGkiOiI5MzFlMDY4Y2E4ZTQ0NWVjODY2YTZkNGQxZGI5ZDBkMiIsInVzZXJfaWQiOiIxIn0.CZ1Ih_DpJhxglyICkIyyGMgCBdO-SmCuPBgFL4MqEW0'


def http_status(path, method='GET', payload=None, headers=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    h = dict(headers or {})
    if data is not None:
        h['Content-Type'] = 'application/json'
    req = Request(URL.rstrip('/') + path, data=data, headers=h, method=method)
    try:
        with urlopen(req, timeout=20) as res:
            return res.status, json.loads(res.read().decode('utf-8'))
    except HTTPError as exc:
        return exc.code, None
    except URLError as exc:
        print('NETWORK ERROR:', type(exc.reason).__name__)
        return 0, None


def jwt_claims(token):
    parts = token.split('.')
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + '=' * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, UnicodeDecodeError, TypeError):
        return None


def main():
    token = API_KEY.strip()
    if token == 'PUT_NEW_TOKEN_HERE' or not token:
        print('ERROR: Put your NEW token in API_KEY first.')
        return
    claims = jwt_claims(token)
    print('Server:', URL)
    print('Project:', PROJECT_ID)
    if claims is not None:
        print('Token format: JWT')
        print('Token type:', claims.get('token_type', 'unknown'))
        exp = claims.get('exp')
        if isinstance(exp, (float, int)):
            print('Expires UTC:', datetime.datetime.fromtimestamp(exp, datetime.timezone.utc).isoformat())
            print('Expired according to local clock:', datetime.datetime.now(datetime.timezone.utc).timestamp() >= exp)
        print('PAT refresh test...')
        status, answer = http_status('/api/token/refresh', method='POST', payload={'refresh': token})
        print('Refresh HTTP status:', status)
        if status == 200 and isinstance(answer, dict) and isinstance(answer.get('access'), str):
            print('Refresh OK; testing project permission...')
            status, _ = http_status(f'/api/projects/{PROJECT_ID}/', headers={'Authorization': 'Bearer ' + answer['access']})
            print('Project read HTTP status:', status)
            if status == 200:
                print('SUCCESS: PAT and project access work.')
            elif status == 403:
                print('PAT works, but project access is forbidden.')
            else:
                print('Project check returned HTTP', status)
        else:
            print('Refresh rejected. Check that this token is a NEW Personal Access Token, and that PAT authentication is enabled for your organization.')
            print('A 403 here is not caused by CSV, dataset or task matching.')
    else:
        print('Token format: Non-JWT (possibly legacy)')
        status, _ = http_status(f'/api/projects/{PROJECT_ID}/', headers={'Authorization': 'Token ' + token})
        print('Legacy project read HTTP status:', status)
        if status == 200:
            print('SUCCESS: Legacy authentication works. Run task linker with --auth legacy.')
        else:
            print('Check legacy token validity, organization token settings and project access.')
    print('Do not share your token or screenshots containing it.')


if __name__ == '__main__':
    main()
