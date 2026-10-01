# Plano de ação — Cursor Usage Bar (macOS + Windows)

## 1. Decisão de stack

| Opção | macOS | Windows | Prós | Contras |
|---|---|---|---|---|
| **Tauri 2 (Rust)** ✅ | Texto + ícone na barra | Ícone + tooltip na bandeja | Um código só, binário pequeno, tray nativo, auto-update e assinatura prontos | Precisa instalar Rust |
| Swift (SwiftUI `MenuBarExtra`) + C# (WinForms `NotifyIcon`) | Nativo perfeito | Nativo perfeito | Melhor UX possível | Dois códigos para manter |
| Electron | Sim | Sim | JS puro | ~150 MB para mostrar um número |
| Python (`rumps` / `pystray`) | Sim | Sim | Rápido de prototipar | Empacotamento ruim, dois toolkits |

**Escolha: Tauri 2 em modo "tray-only"** (sem janela principal). Todo o núcleo (ler token, chamar API, formatar) fica em Rust e é 100% compartilhado. Só o "como exibir" muda por plataforma:

- **macOS:** `TrayIcon::set_title("39%")` — o texto aparece ao lado do ícone na barra de menu.
- **Windows:** a bandeja não exibe texto, então o ícone é **gerado dinamicamente** com o número (ex.: `39`) ou um anel de progresso colorido, e o tooltip mostra o detalhe.

## 2. Arquitetura

```
src-tauri/src/
├── main.rs          # bootstrap Tauri, sem janela, só tray
├── auth.rs          # localiza state.vscdb, lê accessToken (read-only), extrai userId do JWT
├── api.rs           # GET /api/usage-summary com cookie WorkosCursorSessionToken
├── model.rs         # structs serde da resposta (campos opcionais, tolerante a mudanças)
├── tray.rs          # monta título, ícone e menu a partir do UsageSummary
├── icon.rs          # render do ícone com número/anel (Windows; opcional no mac)
├── scheduler.rs     # polling a cada 5 min + refresh manual + backoff em erro
└── settings.rs      # intervalo, métrica exibida, alertas, iniciar com o sistema
```

Fluxo: `scheduler` → `auth` → `api` → `model` → `tray`. Em erro, o tray mostra `—` e o motivo no menu (ex.: "Sessão expirada — abra o Cursor").

## 3. Fases

### Fase 0 — Spike de validação (feito em 30/09/2026)
- [x] Token existe em `cursorAuth/accessToken` no `state.vscdb`.
- [x] `GET https://cursor.com/api/usage-summary` com cookie `WorkosCursorSessionToken` retorna 200 com `autoPercentUsed`, `apiPercentUsed`, `totalPercentUsed`, ciclo e on-demand.
- [ ] Confirmar caminho e formato no Windows (`%APPDATA%\Cursor\User\globalStorage\state.vscdb`).
- [ ] Testar comportamento com token expirado (o Cursor renova sozinho; o app deve apenas reler o banco).

### Fase 1 — MVP macOS (1–2 dias)
1. `npm create tauri-app` com template mínimo; remover janela; ativar feature `tray-icon`.
2. `auth.rs`: abrir SQLite com `rusqlite` em modo `?mode=ro&immutable=1` (o arquivo tem ~2 GB e está em uso pelo Cursor; não pode travar nem escrever).
3. `api.rs`: `reqwest` + `serde`, timeout de 10 s.
4. `tray.rs`: título com `totalPercentUsed` e menu com Auto, API, ciclo, dias restantes, "Atualizar agora", "Abrir dashboard", "Sair".
5. Polling a cada 5 min.
6. Esconder o ícone do Dock (`ActivationPolicy::Accessory`).

**Critério de pronto:** rodando na barra de menu do Mac com os mesmos números do dashboard web.

### Fase 2 — Robustez e UX (1 dia)
- Cores por faixa: verde < 70%, amarelo 70–90%, vermelho > 90%.
- Escolher qual métrica aparece na barra (Total, Auto ou API).
- Notificação nativa ao cruzar 80% e 95% (uma vez por ciclo).
- Iniciar com o sistema (`tauri-plugin-autostart`).
- Backoff exponencial em erro de rede; mensagem clara se o Cursor não estiver instalado ou logado.
- Testes unitários do parser com fixtures JSON (inclusive campos ausentes).

### Fase 3 — Windows (1–2 dias)
- Resolver caminho via `dirs::config_dir()` → `%APPDATA%\Cursor\...`.
- `icon.rs`: gerar ícone 32×32 com o número usando `image` + `ab_glyph` (ou um anel de progresso).
- Tooltip com o resumo; menu igual ao do mac.
- Testar em Windows 10 e 11 (VM ou máquina física).

### Fase 4 — Distribuição (1 dia)
- GitHub Actions com `tauri-action`: build `.dmg` (universal arm64 + x64) e `.msi`/`.exe`.
- Releases no GitHub com changelog.
- Assinatura:
  - macOS: Developer ID + notarização (US$ 99/ano). Sem isso, o usuário precisa liberar em "Privacidade e Segurança".
  - Windows: opcional no início (SmartScreen vai avisar).
- Auto-update via `tauri-plugin-updater` apontando para os releases.
- Opcional: fórmula Homebrew (`brew install --cask cursor-usage-bar`) e Winget.

### Fase 5 — Extras (backlog)
- Mostrar gasto on-demand em US$ quando ativo.
- Suporte a planos de time (`teamUsage`).
- Gráfico simples de consumo diário (guardar snapshots locais).
- Projeção: "no ritmo atual, o limite acaba em X dias".

## 4. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Endpoint não documentado muda | App para de mostrar dados | Parser tolerante (todos os campos `Option`), fallback para `/api/dashboard/get-current-period-usage`, versão rápida de correção via auto-update |
| `state.vscdb` travado ou muito grande | Leitura lenta/erro | Abrir read-only/immutable, consultar só uma chave, cachear token em memória até receber 401 |
| Token expira | 401 | Reler o banco (o Cursor renova sozinho); se persistir, pedir para abrir o Cursor |
| Gatekeeper/SmartScreen bloqueiam | Fricção na instalação | Assinar e notarizar na Fase 4 |
| Termos de uso do Cursor | Baixo (mesma chamada do dashboard, com o token do próprio usuário, só leitura) | Deixar claro no README que é um projeto não oficial |

## 5. O que preciso de você

- **Nada de MCP ou skill extra** para o MVP: o token já está na sua máquina e o GitHub CLI já está autenticado.
- **Instalar Rust** antes da Fase 1: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`.
- **Acesso a um Windows** (VM ou PC) para a Fase 3.
- **Decidir sobre a conta Apple Developer** (US$ 99/ano) antes da Fase 4, se quiser distribuir sem aviso de segurança.

## 6. Estimativa total

~5–7 dias de trabalho focado até ter `.dmg` e `.msi` publicados no GitHub Releases.
