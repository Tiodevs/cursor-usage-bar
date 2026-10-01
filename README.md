# Cursor Usage Bar

App leve que mostra, na barra de menu do macOS (e na bandeja do Windows), quanto do limite do plano do [Cursor](https://cursor.com) ainda está disponível.

```
◐ 39%        ← barra de menu
├─ Auto + Composer   34,4% usado
├─ API (modelos nomeados) 81,5% usado
├─ Total             38,7% usado
├─ Ciclo: 18/09 → 18/10 (18 dias restantes)
├─ On-demand: desativado
├─ Atualizar agora
├─ Abrir dashboard do Cursor
└─ Sair
```

## Status

Em planejamento. Veja o [plano de ação](docs/plano-de-acao.md).

## Como funciona

1. Lê o token de sessão que o próprio Cursor já guarda localmente (nada de login extra):
   - macOS: `~/Library/Application Support/Cursor/User/globalStorage/state.vscdb`
   - Windows: `%APPDATA%\Cursor\User\globalStorage\state.vscdb`
   - Chave SQLite: `ItemTable` → `cursorAuth/accessToken`
2. Monta o cookie `WorkosCursorSessionToken=<userId>%3A%3A<accessToken>`. O `userId` vem do campo `sub` do JWT (parte depois de `|`).
3. Chama `GET https://cursor.com/api/usage-summary` a cada N minutos.
4. Mostra o percentual na barra/bandeja e os detalhes no menu.

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

O endpoint **não é uma API pública documentada** do Cursor. É o mesmo que o dashboard web usa e pode mudar sem aviso. O app precisa tratar falhas com elegância (mostrar `—` e o erro no menu) em vez de quebrar.

## Privacidade

- O token nunca sai da máquina, exceto na chamada HTTPS para `cursor.com`.
- Nada é logado, salvo em disco ou enviado para terceiros.
- O banco do Cursor é aberto **somente leitura**.

## Stack

[Tauri 2](https://tauri.app) (núcleo em Rust) — um único código para macOS e Windows, binário pequeno (~5–10 MB), ícone de bandeja nativo. Justificativa no plano de ação.

## Licença

MIT
