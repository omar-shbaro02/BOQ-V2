# Local Evaluation Installer

The installer runs the web application, API, PostgreSQL, migrations, and local evidence storage as
containers. It is intended for Phase 12 usability testing and demonstrations on a trusted machine.
It is not a production package: production identity, object storage, malware scanning, TLS, secret
management, backup, and recovery adapters remain deliberately fail-closed or unconfigured.

## Windows 10/11

1. Install and start Docker Desktop with Linux containers enabled.
2. Extract the VAI Windows archive to a normal local folder.
3. Right-click `install-windows.ps1` and run it with PowerShell, or execute:

   `powershell -ExecutionPolicy Bypass -File .\install-windows.ps1`

4. Open `http://localhost:3000` if the browser does not open automatically.

Use `-Stop` to stop while preserving data. Use `-ResetData` only when you intentionally want to
remove the local database and uploaded evidence volumes.

## Linux

Install Docker Engine plus Compose, or Podman plus a Compose provider. Then extract the Linux
archive and run:

```bash
chmod +x install-linux.sh
./install-linux.sh
```

Use `./install-linux.sh stop` to stop while preserving data. Use `./install-linux.sh reset` to remove
the local database and evidence volumes.

## Ports and data

- Web interface: `http://localhost:3000`
- API and OpenAPI: `http://localhost:8000` and `http://localhost:8000/docs`
- PostgreSQL is not published to the host by the installer.
- Database and evidence content use named container volumes and survive ordinary stop/start cycles.

Do not expose ports 3000 or 8000 to an untrusted network. The development identity adapter accepts
the actor/project context entered in the UI and exists only to support local evaluation.
