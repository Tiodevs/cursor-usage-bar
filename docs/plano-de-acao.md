# Plano de ação — Cursor Usage Bar (macOS + Windows)

## 1. Decisão de stack

**Python**, com um toolkit de bandeja por plataforma:

- **macOS:** [`rumps`](https://github.com/jaredks/rumps) — texto direto na barra de menu (`◑ 39%`), menu nativo, notificações.
- **Windows:** [`pystray`](https://github.com/moses-palmer/pystray) + `Pillow` — a bandeja não aceita texto, então o ícone é gerado com o número e a cor da faixa de uso.

O núcleo (`core.py`) usa só a biblioteca padrão (`sqlite3`, `urllib`, `json`) e é 100% compartilhado. Cada app de plataforma tem ~100 linhas.

Tradeoffs aceitos em relação a Tauri/Swift: empacotamento mais trabalhoso (py2app / PyInstaller) e binário maior (~20–40 MB). Em troca: zero toolchain extra, iteração rápida e código simples de manter.

## 2. Arquitetura

```
cursor_usage_bar/
├── __main__.py     # detecta plataforma e chama mac_app.run() ou windows_app.run()
├── core.py         # state_db_path, read_access_token, fetch_usage, Usage, formatação
├── settings.py     # preferências e controle de alertas por ciclo
├── mac_app.py      # rumps.App + Timer + esconder ícone do Dock
└── windows_app.py  # pystray.Icon + thread de polling + render_icon (Pillow)
```

Fluxo: timer → `core.fetch_usage()` → atualiza título/ícone e menu. Em erro (`UsageError` / `AuthError`), mostra `—` e o motivo no menu (ex.: "Sessão expirada — abra o Cursor").

## 3. Fases

### Fase 0 — Validação ✅
- [x] Token em `cursorAuth/accessToken` no `state.vscdb`.
- [x] `GET /api/usage-summary` com cookie `WorkosCursorSessionToken` retorna 200 com `autoPercentUsed`, `apiPercentUsed`, `totalPercentUsed`, ciclo e on-demand.
- [ ] Confirmar caminho e formato no Windows (`%APPDATA%\Cursor\User\globalStorage\state.vscdb`).
- [ ] Testar comportamento com token expirado (o Cursor renova sozinho; o app relê o banco a cada atualização).

### Fase 1 — MVP macOS ✅ (30/09/2026)
- [x] `core.py` lendo o SQLite em modo somente leitura e chamando a API (validado contra a conta real).
- [x] `mac_app.py`: título `◑ 39%`, menu com Total, Auto, API, ciclo, on-demand e plano.
- [x] Atualizar agora (⌘R), abrir dashboard, sair (⌘Q).
- [x] Escolher a métrica da barra (Total / Auto / API), salva em `~/.cursor-usage-bar.json`.
- [x] Polling a cada 5 min; ícone do Dock escondido.
- [x] Notificação ao passar de 80% e 95% (uma vez por ciclo).
- [ ] Validar visualmente na barra de menu e o clique em cada item.

### Fase 2 — Robustez (0,5–1 dia)
- Fazer a chamada HTTP em thread separada no Mac (hoje roda no thread da UI, com timeout de 10 s).
- Backoff em erro de rede (1 → 2 → 5 min) em vez de esperar o ciclo cheio.
- Testes com `pytest` para `Usage.from_api` (fixtures com campos ausentes, `isUnlimited`, on-demand ativo) e `user_id_from_token`.
- Cor no título do Mac via `NSAttributedString` (verde/amarelo/vermelho).
- Iniciar com o sistema: LaunchAgent no Mac (`~/Library/LaunchAgents/*.plist`).

### Fase 3 — Windows (1 dia)
- [x] `windows_app.py` com ícone gerado (verde < 70, amarelo 70–89, vermelho ≥ 90), tooltip e menu.
- [x] Render do ícone validado no Mac.
- [ ] Rodar em Windows 10/11 real: caminho do banco, fonte `segoeuib.ttf`, notificações (`icon.notify`).
- [ ] Iniciar com o sistema: atalho em `shell:startup` ou chave `HKCU\...\Run`.

### Fase 4 — Empacotamento e distribuição (1–2 dias)
- **macOS:** `py2app` gerando `Cursor Usage Bar.app` com `LSUIElement=true` no `Info.plist`; empacotar em `.dmg` (`create-dmg`).
- **Windows:** `PyInstaller --onefile --noconsole` gerando `.exe`; opcional instalador com Inno Setup.
- GitHub Actions com matriz `macos-latest` + `windows-latest` publicando os artefatos no GitHub Releases a cada tag `v*`.
- Assinatura:
  - macOS: Developer ID + notarização (US$ 99/ano). Sem isso, o usuário libera em "Privacidade e Segurança".
  - Windows: opcional no início (SmartScreen vai avisar). PyInstaller sem assinatura às vezes gera falso positivo de antivírus.
- Opcional: Homebrew Cask e Winget.

### Fase 5 — Extras (backlog)
- Mostrar gasto on-demand em US$ na barra quando ativo.
- Suporte a planos de time (`teamUsage`).
- Histórico local e projeção: "no ritmo atual, o limite acaba em X dias".
- Janela de preferências (intervalo, limiares de alerta).

## 4. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Endpoint não documentado muda | App para de mostrar dados | Parser tolerante (todos os campos opcionais); fallback para `POST /api/dashboard/get-current-period-usage`; release rápida |
| `state.vscdb` grande (~2 GB) e em uso pelo Cursor | Leitura lenta/travada | Conexão `mode=ro`, timeout de 5 s, consulta de uma única chave |
| Token expira | 401 | Relê o banco a cada atualização; se persistir, pede para abrir o Cursor |
| Empacotamento Python (py2app/PyInstaller) | Builds frágeis, binário grande | CI com build nas duas plataformas a cada tag; fixar versões no `requirements.txt` |
| Gatekeeper / SmartScreen / antivírus | Fricção na instalação | Assinar e notarizar na Fase 4 |

## 5. O que preciso de você

- **Nada de MCP ou skill extra.**
- Conferir o app na barra de menu e me dizer se algo está estranho.
- **Acesso a um Windows** (VM ou PC) para a Fase 3.
- **Decidir sobre a conta Apple Developer** antes da Fase 4, se quiser distribuir sem aviso de segurança.

## 6. Estimativa restante

~3–4 dias de trabalho focado até ter `.dmg` e `.exe` publicados no GitHub Releases.
