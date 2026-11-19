# FROM pro97775/wzmlx:wzadv
FROM pro97775/heroku:ariaqbit

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

COPY requirements.txt .
RUN uv pip uninstall --python /wzvenv/bin/python pyrotgfork || true
RUN uv pip uninstall --python /wzvenv/bin/python pyrogram || true
RUN uv pip uninstall --python /wzvenv/bin/python pytgcrypto || true
RUN uv pip install --python /wzvenv/bin/python --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["bash", "start.sh"]
