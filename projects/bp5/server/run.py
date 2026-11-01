"""Restricted service entry: one worker owns the bounded audio queue."""
import os
import uvicorn

if __name__ == '__main__':
    os.umask(0o077)
    uvicorn.run(
        'production:app',
        host=os.environ.get('HOST', '127.0.0.1'),
        port=int(os.environ.get('PORT', '8788')),
        workers=1,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips='127.0.0.1',
        timeout_keep_alive=5,
        timeout_graceful_shutdown=20,
        limit_concurrency=48,
    )
