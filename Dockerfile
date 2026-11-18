FROM pro97775/heroku:ownv3

WORKDIR /usr/src/app

COPY requirements.txt .
RUN uv pip uninstall --python /wzvenv/bin/python pyrotgfork || true
RUN uv pip uninstall --python /wzvenv/bin/python pyrogram || true
RUN uv pip install --python /wzvenv/bin/python --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["bash", "start.sh"]
