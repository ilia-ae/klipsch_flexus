# Klipsch Flexus

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#descoberta-automática)

[![Validate](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)
[![Hassfest](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/hassfest.yaml)
[![CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | [Español](README_es.md) | **Português**

---

Integração personalizada do Home Assistant para soundbars **Klipsch Flexus** — controle via **API HTTP local nativa**, sem nuvem, sem atrasos.

> ✅ **Atualizado até a v2.5.15 (2026-06-14)** — **41 entidades**, todos os comandos de escrita verificados ao vivo contra o firmware de 2026 (assinados com HMAC), controláveis em standby. Os selos acima refletem a versão publicada e o último push.

## 📸 Painel (Dashboard)

Um painel Lovelace personalizado inteiramente baseado nas entidades da integração — entrada, modo de som, noite/diálogo, presets de EQ, filtro Dirac, tom (graves/médios/agudos), níveis dos canais surround e subwoofers — tudo ao vivo pela API local.

![Painel Klipsch Flexus](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**Componentes HACS necessários** (todos instaláveis via [HACS](https://github.com/hacs/integration)):

| Componente | Repositório | Para quê |
|------------|-------------|----------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | esta integração — as entidades |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | cartão do reprodutor |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | botões de entrada/modo/EQ com estilo dinâmico |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | destaque do estado ativo (CSS) |

📋 **YAML completo do painel + esquema de cores:** [docs/DASHBOARD.md](DASHBOARD.md)

### Modelos compatíveis

| Modelo | Canais | Recursos |
|--------|--------|----------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live, Dolby Atmos, 13 drivers |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos up-firing |
| **Flexus CORE 100** | 2.1 | Virtual Dolby Atmos |

> A soundbar deve ser **totalmente configurada primeiro no aplicativo oficial Klipsch Connect Plus** — conclua todo o processo de configuração pelo menos uma vez (Wi-Fi, atualização de firmware, pareamento de caixas, calibração Dirac). No firmware de 2026 isso também provisiona a credencial de assinatura dos comandos, então uma configuração incompleta deixa a maioria dos comandos sem autorização. Esta integração cuida apenas do controle diário.

## ⚠️ Compatibilidade de firmware (atualização 2026)

Uma atualização de firmware de 2026 (**Device Version `1.1.3.x`**, ex. `1.1.3.0x7cd294e`, build do Cast `20250512_0201_RC25`) mudou a API HTTP local de duas formas:

1. **`setData` agora exige `POST` com corpo JSON.** O antigo `GET /api/setData?...` retorna `405 Strict HTTP required!`. **Corrigido na v2.4.1** — atualize a integração.
2. **A maioria das escritas `setData` agora exige autenticação** (`settings:/webserver/authMode = setData`). Comandos protegidos respondem `401 Forbidden` com `WWW-Authenticate: HMAC_SHA256_AES256`. **Corrigido na v2.5.0** — a integração agora assina essas escritas automaticamente.

### O que funciona no novo firmware

| Recurso | Status |
|---------|--------|
| Todos os sensores / leituras de status (`getData`) | ✅ Funciona |
| Volume, mudo (Mute) | ✅ Funciona |
| Entrada, modo de som, noite/diálogo, graves/médios/agudos, preset de EQ, Dirac, níveis de subwoofer e surround, energia | ✅ Funciona (assinado com HMAC, v2.5.0+) |
| LED, lip-sync, balanço, loudness, não perturbe, standby automático + 4 outros interruptores | ✅ Funciona (assinado; adicionado na v2.5.8–2.5.9) — também em standby |

O status ao vivo de cada comando aparece em **Download diagnostics** (seção `command_health`, adicionada na v2.4.2).

### Status da correção

✅ **Resolvido na v2.5.0 — controle completo restaurado, nenhuma ação do usuário necessária.** A assinatura de requisições `HMAC_SHA256_AES256` agora está implementada. A credencial do dispositivo é derivada automaticamente do endereço MAC da soundbar (que a integração já detecta), então **não há nada para configurar** — basta atualizar a integração. Desde a **v2.5.9** o MAC é lido de forma determinística do próprio dispositivo (`settings:/system/primaryMacAddress`), de modo que a resolução funciona na primeira tentativa em todas as unidades (mantendo a descoberta anterior via registro/ARP como fallback). As escritas assinadas vão para o endpoint HTTPS do dispositivo; volume/mudo continuam funcionando sem assinatura.

> Requer o pacote `cryptography` (declarado no manifesto; incluído no Home Assistant, portanto já presente).

📖 **Como fizemos a engenharia reversa** — a história completa da investigação (blutter, Frida, WireGuard-MITM, a análise do «teatro de segurança»): [relatório](REPORT_en.md) (em inglês; russo: [REPORT.md](REPORT.md)).

Firmware mais antigo (anterior à `1.1.3`) não é afetado e mantém o controle completo via fallback `GET`.

## Recursos

### Media Player
- **Volume** — nível, aumentar/diminuir, silenciar
- **Energia** — ligar / standby
- **Fonte de entrada** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast
- **Modo de som** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Reprodução** — play/pausa, próxima/anterior faixa
- **Info de mídia** — título, artista, álbum, capa, app de origem

### Níveis de canal (11 controles, -6 a +6 dB)

| Canal | Descrição |
|-------|-----------|
| Front Height | Alto-falante de altura frontal Dolby Atmos |
| Back Height | Alto-falante de altura traseiro Dolby Atmos |
| Side Left / Right | Alto-falantes surround laterais |
| Back Left / Right | Alto-falantes surround traseiros |
| Subwoofer Wireless 1 / 2 | Níveis do subwoofer sem fio |
| Bass / Mid / Treble | Controles de equalização |

### Configurações de áudio (Selects)
- **Predefinição EQ** — Flat, Bass, Rock, Vocal
- **Modo noturno** — reduz a faixa dinâmica para audição silenciosa
- **Modo diálogo** — melhora a clareza da fala (3 níveis)
- **Dirac Live** — filtro de correção de sala (detectado automaticamente do dispositivo)
- **Brilho do LED** — LED frontal: Off / Dim / Bright

### Números de configuração
- **Atraso de lip-sync** — sincronia A/V manual (0–300 ms)
- **Balanço** — balanço esquerdo/direito (−10…+10)
- **Tempo de inatividade** — tempo ocioso para standby automático (0–3600 s)

### Interruptores (Switches)
- **Lip-sync automático** — atraso A/V automático
- **Bypass de EQ** — ignora o equalizador
- **Energia automática** — comportamento automático de ligar/standby
- **Loudness** — compensação de loudness em volume baixo
- **Não perturbe** — suprime notificações/sons
- **Standby automático** — entra em standby quando ocioso
- **Sons da interface**, **Modos de som extras**, **Pareamento automático do controle BLE**, **Atualização automática de firmware**

> Todas as configurações acima também podem ser escritas enquanto a soundbar está em **standby** (o dispositivo as aplica e mantém); a integração mantém as entidades disponíveis e lembra o valor que você definiu em vez de revertê-lo.

### Diagnósticos
- **Tempo de resposta** — duração da consulta API em ms, contadores de requisições/erros
- **Status do dispositivo** — Ligado / Standby / Offline com info do decodificador, entrada e modo de som
- **MAC de assinatura** — o MAC usado para assinar escritas no firmware de 2026 (esquema, candidatos, estado resolvido)
- **Link de rede** — interface ativa com fio/sem fio, nomes das interfaces, origens do MAC
- **Modo de operação** / **Teste de caixas** — estado do dispositivo somente leitura (exibido, deliberadamente não controlável)
- **Atrasos das caixas** (sub com fio/sem fio, surround sem fio) — somente leitura, autocalibrados pelo dispositivo
- **Baixar diagnósticos** — exportação completa do estado (Configurações > Dispositivos > Klipsch Flexus > Baixar diagnósticos)

### Traduções
Tradução completa da interface em **7 idiomas**: inglês, russo, alemão, espanhol, francês, italiano, português. Todos os nomes de entidades, estados e telas de configuração estão traduzidos.

## Instalação

### HACS (recomendado)

1. Abra **HACS** > Integrações > pesquise **Klipsch Flexus**
2. Instale e reinicie o Home Assistant
3. A soundbar deve ser **descoberta automaticamente** — verifique as notificações
4. Ou vá para **Configurações** > Dispositivos e serviços > **Adicionar integração** > Klipsch Flexus

### Manual

1. Copie `custom_components/klipsch_flexus/` para o diretório `config/custom_components/` do seu HA
2. Reinicie o Home Assistant
3. Adicione a integração em Configurações > Dispositivos e serviços

## Descoberta automática

A soundbar é descoberta automaticamente na sua rede via **mDNS / Zeroconf** (protocolo Google Cast).

Com a soundbar ligada, o Home Assistant mostrará uma notificação:
> Encontrado **Klipsch Flexus CORE 300** em `192.168.1.100`. Deseja adicionar esta soundbar?

**Como funciona:**
- A soundbar se anuncia como `Flexus-Core-*` via serviço mDNS `_googlecast._tcp`
- A integração identifica o dispositivo pelos registros TXT `md` (modelo) e `fn` (nome)
- Dispositivos proxy AirCast são filtrados automaticamente

Se a descoberta automática não funcionar (ex.: isolamento de rede), você sempre pode adicionar a integração manualmente informando o endereço IP.

## Configuração

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| Host | — | Endereço IP da soundbar (obrigatório) |
| Intervalo de consulta | 15 s (60 s em standby) | Configurável em Opções (5–120 s); reduzido automaticamente em modo de espera |

**Dica:** Atribua um IP estático / reserva DHCP à soundbar.

Você pode alterar o IP depois em **Reconfigurar** (Configurações > Dispositivos > Klipsch Flexus > Reconfigurar).

## Como funciona

A soundbar disponibiliza uma API HTTP local na porta 80:
- `GET /api/getData` — ler parâmetros
- `POST /api/setData` — escrever parâmetros (corpo JSON; fallback para GET em firmware antigo)
- `GET /api/getRows` — listar dados estruturados (filtros Dirac)

### Design resiliente para um dispositivo lento

O Klipsch Flexus tem um **servidor HTTP single-thread** que processa uma requisição por vez. A integração é construída em torno dessa limitação:

| Mecanismo | Descrição |
|-----------|-----------|
| Serialização de requisições | Todas as chamadas API passam por `asyncio.Lock` — sem concorrência |
| Retry com espera | Erros temporários reexecutados 2x com 0,5 s de espera |
| Timeouts adaptativos | 8 s leitura, 10 s escrita, 15 s comandos de energia |
| Degradação elegante | Leituras falhas usam os últimos valores conhecidos |
| Atualizações otimistas | UI atualiza instantaneamente, depois verificado por polling; valores aplicados em standby são mantidos em cache para que o polling de standby nunca os reverta |
| **Polling com detecção de standby** | Estado de energia verificado primeiro; em standby apenas 1 requisição ao invés de 20+, valores em cache preservados, intervalo reduzido para 60 s. As configurações permanecem **disponíveis e controláveis** em standby — o dispositivo aplica as escritas e a integração as lembra |

## Entidades

![Página do dispositivo Klipsch Flexus no Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*A página do dispositivo no Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + interruptores) e o registo de atividade.*

| Entidade | Tipo | Categoria |
|----------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Modo noturno / Modo diálogo / Predefinição EQ / Filtro Dirac / Brilho do LED | Select (x5) | Configuração |
| Back Height / Left / Right, Front Height, Side Left / Right | Number (x6) | Configuração |
| Subwoofer Wireless 1 / 2 | Number (x2) | Configuração |
| Bass / Mid / Treble | Number (x3) | Configuração |
| Atraso de lip-sync, Balanço, Tempo de inatividade | Number (x3) | Configuração |
| Lip-sync automático, Bypass de EQ, Energia automática, Sons da interface, Modos de som extras, Pareamento automático do controle BLE, Atualização automática de firmware | Switch (x7) | Configuração |
| Loudness, Não perturbe, Standby automático | Switch (x3) | Configuração |
| Tempo de resposta, Status do dispositivo, Entrada ativa, Modo de som ativo | Sensor (x4) | Diagnóstico |
| MAC de assinatura, Link de rede | Sensor (x2) | Diagnóstico |
| Modo de operação, Teste de caixas, Atraso do sub com fio/sem fio, Atraso surround | Sensor (x5, somente leitura) | Diagnóstico |

**Total: 41 entidades** (1 media player + 5 selects + 14 numbers + 10 switches + 11 sensors)

## Solução de problemas

| Problema | Solução |
|----------|---------|
| Não conecta | Verifique se a soundbar está na mesma rede. Tente: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entidades indisponíveis | O app Klipsch pode estar consultando simultaneamente — feche-o |
| Atualizações lentas | Aumente o intervalo de consulta em Opções |
| Integração não carrega | Verifique os logs do HA por erros de importação. Requer HA 2024.11+ |

## Limitações conhecidas

- Uma soundbar por entrada de integração (adicione várias separadamente)
- Sem gerenciamento de multi-room / grupos surround sem fio (use Klipsch Connect Plus)
- AirPlay e Cast não são utilizados — apenas a API HTTP nativa
- A configuração inicial deve ser concluída **por completo** no app oficial Klipsch Connect Plus — todo o processo pelo menos uma vez (isso provisiona a credencial de escrita do firmware de 2026)

## Licença

MIT — ver [LICENSE](../LICENSE).
