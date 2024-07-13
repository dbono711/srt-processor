LOG_FILE = logs/setup.log
CUR_DIR = $(shell pwd)
VENV_DIR = .venv
REQ_FILE = requirements.txt
STREAMLIT_APP = app.py
STREAMLIT_PORT = 8501
STREAMLIT_SERVICE = srt_processor

define log
	echo "[$(shell date '+%Y-%m-%d %H:%M:%S')] $1" >> $(LOG_FILE)
endef

define SERVICE
[Unit]
Description=$(STREAMLIT_SERVICE)
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=$(CUR_DIR)
ExecStart=$(CUR_DIR)/.venv/bin/python -m streamlit run --server.port=$(STREAMLIT_PORT) $(STREAMLIT_APP)
SyslogIdentifier=$(STREAMLIT_SERVICE)
Restart=always
RestartSec=1

PrivateTmp=yes
ProtectHome=read-only
NoNewPrivileges=yes

ProtectSystem=full

[Install]
WantedBy=multi-user.target
endef
export SERVICE

.PHONY: initialize-log initialize-venv service start

initialize-log:
	@echo -n "" > $(LOG_FILE)

initialize-venv: initialize-log
	@if [ ! -d $(VENV_DIR) ]; then \
		$(call log,Creating virtual environment...); \
		python_bin -m venv $(VENV_DIR) >> $(LOG_FILE) 2>&1; \
		$(call log,Installing requirements in virtual environment...); \
		$(VENV_DIR)/bin/pip install --upgrade pip >> $(LOG_FILE) 2>&1; \
		$(VENV_DIR)/bin/pip install -r $(REQ_FILE) >> $(LOG_FILE) 2>&1; \
	else \
		$(call log,Virtual environment already exists.); \
	fi

service: initialize-venv
	@if [ -e /etc/systemd/system/$(STREAMLIT_SERVICE).service ]; then \
		$(call log,Systemd service exists.); \
	else \
		echo "$$SERVICE" | sudo tee /etc/systemd/system/$(STREAMLIT_SERVICE).service > /dev/null; \
		$(call log,Systemd service created.); \
	fi

start: service
	$(call log,Starting system service.)
	sudo systemctl daemon-reload
	sudo systemctl enable $(STREAMLIT_SERVICE).service
	sudo systemctl start $(STREAMLIT_SERVICE).service
	$(call log,System service started.)

all: start
