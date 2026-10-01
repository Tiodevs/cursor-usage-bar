# Cursor Usage Bar

App leve que mostra, na barra de menu do macOS (e na bandeja do Windows), quanto do limite do plano do [Cursor](https://cursor.com) você já usou.

```
◑ 39%                          ← barra de menu (macOS)
├─ Total: 39% usado
├─ Auto + Composer: 34% usado
├─ API (modelos nomeados): 83% usado
├─ Ciclo: 18/09 → 18/10 (17 dias restantes)
├─ On-demand: desativado
├─ Plano: pro
├─ Atualizado às 22:20
├─ Atualizar agora         ⌘R
├─ Abrir dashboard do Cursor
├─ Mostrar na barra ▸ Total / Auto + Composer / API
└─ Sair                    ⌘Q
```

No Windows, a bandeja não exibe texto: o ícone é desenhado com o número (verde < 70%, amarelo 70–89%, vermelho ≥ 90%) e o resumo aparece no tooltip.

## Status

MVP funcional no macOS. Windows implementado, ainda não testado em máquina real. Veja o [plano de ação](docs/plano-de-acao.md).

## Rodar localmente

Requer Python 3.10+ e o Cursor instalado e logado.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m cursor_usage_bar
```

O `requirements.txt` instala só o que a plataforma precisa: `rumps` no macOS, `pystray` + `Pillow` no Windows.

## Estrutura

```
cursor_usage_bar/
├── __main__.py     # escolhe o app pela plataforma
├── core.py         # token, chamada da API e formatação (só biblioteca padrão)
├── settings.py     # ~/.cursor-usage-bar.json: métrica, intervalo, alertas
├── mac_app.py      # barra de menu com rumps
└── windows_app.py  # bandeja com pystray + ícone gerado com Pillow
```

## Como funciona

1. Lê o token de sessão que o próprio Cursor já guarda localmente (nada de login extra):
   - macOS: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`
   - Windows: `%APPDATA%\Cursor\User\globalStorage\state.vscdb`
   - Chave SQLite: `ItemTable` → `cursorAuth/accessToken`
2. Monta o cookie `WorkosCursorSessionToken=<userId>%3A%3A<accessToken>`. O `userId` vem do campo `sub` do JWT (parte depois de `|`).
3. Chama `GET https://cursor.com/api/usage-summary` a cada 5 minutos.
4. Mostra o percentual na barra/bandeja e os detalhes no menu. Notifica uma vez por ciclo ao passar de 80% e 95%.

### Exemplo de resposta (`/api/usage-summary`)

```json
{
  "billingCycleStart": "2026-09-18T18:58:23.000Z",
  "billingCycleEnd": "2026-10-18T18:58:23.000Z",
  "membershipType": "pro",
  "isUnlimited": false,
  "individualUsage": {
    "plan": {
      "used": 2000,
      "limit": 2000,
      "remaining": 0,
      "autoPercentUsed": 34.4,
      "apiPercentUsed": 81.53,
      "totalPercentUsed": 38.68
    },
    "onDemand": { "enabled": false, "used": 0, "limit": null }
  }
}
```

## Aviso importante

Projeto não oficial. O endpoint **não é uma API pública documentada** do Cursor: é o mesmo que o dashboard web usa e pode mudar sem aviso. Em caso de falha, o app mostra `—` e o erro no menu em vez de quebrar.

## Privacidade

- O token só sai da máquina na chamada HTTPS para `cursor.com`.
- Nada é logado nem enviado para terceiros. O único arquivo gravado é `~/.cursor-usage-bar.json` (preferências).
- O banco do Cursor é aberto **somente leitura**.

## Licença

MIT
