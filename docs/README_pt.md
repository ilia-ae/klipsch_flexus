# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#descoberta-automática)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | [Español](README_es.md) | **Português** | [Français](README_fr.md) | [Italiano](README_it.md) | [Nederlands](README_nl.md) | [中文](README_zh.md)  
🔒 **Segurança**: [Política](../SECURITY.md) | [Relatório de avaliação](SECURITY_ASSESSMENT_CORE_300.md)

---

Integração personalizada do Home Assistant para soundbars **Klipsch Flexus** — controle via **API HTTP local nativa**, sem nuvem, sem atrasos.

> ✅ **42 entidades**. Todos os comandos de escrita foram verificados ao vivo no firmware de 2026 (assinados com HMAC) e funcionam em standby. Cada commit em `main` é testado primeiro localmente: veja [Resultados dos testes](#resultados-dos-testes).

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

A integração não verifica o modelo. Ela adiciona qualquer soundbar Flexus que se anuncie via Google Cast e usa a mesma API local e as mesmas 42 entidades para todos os modelos. O mantenedor testa numa CORE 300. Um controle para hardware que o seu modelo não tem (por exemplo, os canais de altura numa CORE 100) pode falhar com um erro.

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

O status ao vivo de cada comando aparece em **Download diagnostics** (seção `command_health`, adicionada na v2.4.2). Ela é somente leitura: por comando mostra se a configuração pode ser lida e como o dispositivo respondeu às escritas feitas desde o último carregamento da integração (`http_status`, `needs_auth` quando o dispositivo pediu assinatura).

### Status da correção

✅ **Resolvido na v2.5.0 — controle completo restaurado, nenhuma ação do usuário necessária.** A assinatura de requisições `HMAC_SHA256_AES256` agora está implementada. A credencial do dispositivo é derivada automaticamente do endereço MAC da soundbar (que a integração já detecta), então **não há nada para configurar** — basta atualizar a integração. Desde a **v2.5.9** o MAC é lido de forma determinística do próprio dispositivo (`settings:/system/primaryMacAddress`), de modo que a resolução funciona na primeira tentativa em todas as unidades (mantendo a descoberta anterior via registro/ARP como fallback). As escritas assinadas vão para o endpoint HTTPS do dispositivo; volume/mudo continuam funcionando sem assinatura.

> Requer o pacote `cryptography` (incluído no Home Assistant, portanto já presente; não consta como requisito no manifesto).

📖 **Como fizemos a engenharia reversa** — a história completa da investigação (blutter, Frida, WireGuard-MITM, a análise do «teatro de segurança»): [relatório](REPORT_en.md) (em inglês; russo: [REPORT.md](REPORT.md)).

Firmware mais antigo (anterior à `1.1.3`) não é afetado e mantém o controle completo via fallback `GET`.

## Recursos

### Media Player
- **Volume** — nível, aumentar/diminuir, silenciar
- **Energia** — ligar / desligar (standby de rede)
- **Fonte de entrada** — TV ARC, HDMI, SPDIF, Bluetooth, Google Cast. Enquanto um app de streaming (Spotify Connect, TIDAL Connect, QPlay), USB ou a calibração Dirac está ativo, a fonte mostra isso
- **Modo de som** — Movie, Music, Game, Sport, Night, Direct, Surround, Stereo
- **Reprodução** — play/pausa, próxima/anterior faixa
- **Info de mídia** — título, artista, álbum, capa, app de origem

### Níveis de canal (11 controles: 9 de -6 a +6 dB, 2 subwoofers de -12 a +6 dB)

| Canal | Descrição |
|-------|-----------|
| Front Height | Alto-falante de altura frontal Dolby Atmos |
| Back Height | Alto-falante de altura traseiro Dolby Atmos |
| Side Left / Right | Alto-falantes surround laterais |
| Back Left / Right | Alto-falantes surround traseiros |
| Wired Subwoofer / Wireless Subwoofers | Saída de subwoofer com fio (RCA) e subwoofers sem fio (um ou dois, ajustados juntos), -12 a +6 dB |
| Bass / Mid / Treble | Controles de equalização |

### Configurações de áudio (Selects)
- **Predefinição EQ** — Flat, Bass, Rock, Vocal (+ Custom, informado ao alterar Bass / Mid / Treble — pelo HA ou pelo app Klipsch — ou ao definir uma curva própria no app; não pode ser selecionado no HA)
- **Modo noturno** — reduz a faixa dinâmica para audição silenciosa
- **Modo diálogo** — melhora a clareza da fala (3 níveis)
- **Dirac Live** — filtro de correção de sala (detectado automaticamente do dispositivo)
- **Brilho do LED** — LED frontal: Off / Dim / Bright
- **Tempo de inatividade** — tempo ocioso antes do standby automático: Off / 5 / 10 / 15 / 30 min

### Números de configuração
- **Atraso de lip-sync** — sincronia A/V manual (0–500 ms)
- **Balanço** — balanço esquerdo/direito (−10…+10 dB)

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
- **Baixar diagnósticos** — exportação completa do estado (Configurações > Dispositivos > Klipsch Flexus > Baixar diagnósticos). O endereço IP, todos os endereços MAC, o BSSID do Wi-Fi, o ID do dispositivo e as URLs de streaming são ocultados

### Caixas sem fio
- **Um dispositivo por caixa pareada** — as caixas Flexus SUB / SURR (Subwoofer sem fios 1 / 2, Surround esquerdo / direito) aparecem como dispositivos próprios sob a soundbar, com as versões que o app Klipsch Connect Plus mostra (Product Information): firmware MCU, RX e EQ como *Firmware*, a versão de hardware e o número do modelo
- **Conectado** — um sensor por caixa: ligado se o link sem fio da caixa estava ativo na última leitura, desligado se estava caído
- **Quando são lidas** — uma vez após a configuração e quando você pressiona **Ler caixas sem fios** (um botão da soundbar), para que a consulta regular continue tão leve quanto antes. Para acompanhar as quedas ao vivo, ative **Monitorizar caixas sem fios** em Opções: o link passa a ser lido a cada consulta (uma requisição a mais), e um subwoofer que perde a conexão aparece no histórico do sensor Conectado. Os sensores monitorados ficam indisponíveis em standby
- Uma caixa ganha seu dispositivo assim que é vista conectada, e o mantém enquanto estiver despareada ou offline. O dispositivo de uma caixa despareada pode ser excluído na página do dispositivo

### Traduções
Tradução completa da interface em **9 idiomas**: inglês, russo, alemão, espanhol, francês, italiano, português, neerlandês, chinês simplificado (`zh-Hans`). Todos os nomes de entidades, estados e telas de configuração estão traduzidos.

## Instalação

### HACS (recomendado)

O Klipsch Flexus está na loja padrão do HACS, então você não precisa adicionar um repositório personalizado.

[![Abra a sua instância do Home Assistant e este repositório no HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. Use o botão acima para abrir o Klipsch Flexus no seu HACS (link do My Home Assistant), ou abra o **HACS** e pesquise **Klipsch Flexus**
2. Selecione **Baixar** e reinicie o Home Assistant
3. A soundbar deve ser **descoberta automaticamente** — verifique as notificações
4. Ou vá para **Configurações** > Dispositivos e serviços > **Adicionar integração** > Klipsch Flexus

### Manual

1. Copie `custom_components/klipsch_flexus/` para o diretório `config/custom_components/` do seu HA
2. Reinicie o Home Assistant
3. Adicione a integração em Configurações > Dispositivos e serviços

### Atualização

Depois de atualizar a integração (HACS ou manual), **reinicie o Home Assistant**: o HA carrega o código Python da integração na inicialização, então a nova versão só roda após um reinício. Alterar as **Opções** ou **Reconfigurar** o host tem efeito imediato, sem reinício (a entrada é recarregada).

### Versões beta

Novos recursos e correções saem primeiro como **beta**: uma pre-release do GitHub com a tag `vX.Y.Z-beta.N`. A versão estável `vX.Y.Z` vem depois. O HACS só oferece uma beta a quem optar por ela. Se você não fizer nada, continua nas versões estáveis e não recebe avisos de betas.

Para receber betas (HACS 2.x; os nomes estão em inglês, o seu HACS pode mostrá-los traduzidos):

1. Vá em **Configurações** > Dispositivos e serviços > **HACS** e abra a entrada de serviço **Klipsch Flexus** (o HACS cria uma para cada repositório baixado)
2. Encontre o interruptor **Pre-release** (uma entidade de diagnóstico). Ele vem desativado: abra-o, selecione o ícone de engrenagem, ative a entidade e salve
3. Ligue o **Pre-release**. O HACS passa a oferecer a beta mais recente como atualização. Para verificar na hora, abra o Klipsch Flexus no HACS e selecione **Update information** no menu ⋮
4. Instale a atualização e reinicie o Home Assistant

Para voltar à versão estável, desligue o **Pre-release**. O HACS volta a oferecer apenas versões estáveis, e você fica com a beta até que a próxima versão estável a substitua. Para voltar imediatamente, abra o Klipsch Flexus no HACS, selecione ⋮ > **Redownload** > **Need a different version?**, escolha a versão mais recente sem a marca *pre-release*, baixe-a e reinicie o Home Assistant.

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
| Intervalo de consulta | 15 s | Configurável em Opções (5–120 s). Em standby a integração consulta sempre a cada 60 s |
| Monitorizar caixas sem fios | desligado | Só em Opções. Verifica a cada consulta se cada subwoofer / surround sem fio está conectado (uma requisição a mais), para que as quedas apareçam no seu sensor **Conectado**. Desligado: lido após a configuração e com o botão **Ler caixas sem fios** |
| MAC do dispositivo | detectado automaticamente | Só em Opções (opcional). Substitui o MAC usado para assinar as escritas do firmware de 2026; só é necessário se comandos além de volume/mudo falharem (veja o sensor de diagnóstico **MAC de assinatura**) |

**Dica:** Atribua um IP estático / reserva DHCP à soundbar.

Você pode alterar o IP depois em **Reconfigurar** (Configurações > Dispositivos > Klipsch Flexus > Reconfigurar).

## Como funciona

A soundbar disponibiliza uma API HTTP local na porta 80:
- `GET /api/getData` — ler parâmetros
- `POST /api/setData` — escrever parâmetros (corpo JSON; fallback para GET em firmware antigo)
- `GET /api/getRows` — listar dados estruturados (filtros Dirac)

No firmware de 2026, as escritas assinadas com HMAC vão para `POST https://<IP>/api/setData`.

### Design resiliente para um dispositivo lento

O Klipsch Flexus tem um **servidor HTTP single-thread** que processa uma requisição por vez. A integração é construída em torno dessa limitação:

| Mecanismo | Descrição |
|-----------|-----------|
| Serialização de requisições | Todas as chamadas API passam por `asyncio.Lock` — sem concorrência |
| Retry com espera | Escritas (exceto controles de mídia) e a verificação de energia reexecutadas 2x com 0,5 s de espera; as leituras do polling não são repetidas (valor em cache), e dois timeouts seguidos encerram o polling como offline |
| Timeouts adaptativos | 8 s leitura, 10 s escrita, 15 s comandos de energia |
| Degradação elegante | Leituras falhas usam os últimos valores conhecidos |
| Atualizações otimistas | UI atualiza instantaneamente e mantém o valor escrito até o próximo polling regular, que o relê (o polling ~1 s após um comando busca seus efeitos colaterais, p. ex. o decodificador após trocar de entrada); valores aplicados em standby são mantidos em cache para que o polling de standby nunca os reverta |
| **Polling com detecção de standby** | Estado de energia verificado primeiro; o primeiro polling após a configuração lê tudo uma vez, mesmo em standby — depois, em standby apenas 1 requisição ao invés de ~40, valores em cache preservados, intervalo reduzido para 60 s. As configurações permanecem **disponíveis e controláveis** em standby — o dispositivo aplica as escritas e a integração as lembra |

## Entidades

![Página do dispositivo Klipsch Flexus no Home Assistant](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*A página do dispositivo no Home Assistant — Device info, Controls, Configuration (Night / Dialog / EQ / Dirac / LED + interruptores) e o registo de atividade.*

| Entidade | Tipo | Categoria |
|----------|------|-----------|
| Klipsch Flexus CORE 300 | Media Player | — |
| Modo noturno / Modo diálogo / Predefinição EQ / Filtro Dirac / Brilho do LED / Tempo de inatividade | Select (x6) | Configuração |
| Back Height / Left / Right, Front Height, Side Left / Right | Number (x6) | Configuração |
| Wired Subwoofer / Wireless Subwoofers | Number (x2) | Configuração |
| Bass / Mid / Treble | Number (x3) | Configuração |
| Atraso de lip-sync, Balanço | Number (x2) | Configuração |
| Lip-sync automático, Bypass de EQ, Energia automática, Sons da interface, Modos de som extras, Pareamento automático do controle BLE, Atualização automática de firmware | Switch (x7) | Configuração |
| Loudness, Não perturbe, Standby automático | Switch (x3) | Configuração |
| Tempo de resposta, Status do dispositivo, Entrada ativa, Modo de som ativo | Sensor (x4) | Diagnóstico |
| MAC de assinatura, Link de rede | Sensor (x2) | Diagnóstico |
| Modo de operação, Teste de caixas, Atraso do sub com fio/sem fio, Atraso surround | Sensor (x5, somente leitura) | Diagnóstico |
| Ler caixas sem fios | Button | Diagnóstico |
| Conectado (no dispositivo de cada caixa sem fio) | Binary Sensor (um por caixa pareada, até 4) | Diagnóstico |

**Total: 42 entidades** (1 media player + 6 selects + 13 numbers + 10 switches + 11 sensors + 1 button), mais um sensor Conectado por caixa sem fio pareada

## Solução de problemas

| Problema | Solução |
|----------|---------|
| Não conecta | Verifique se a soundbar está na mesma rede. Tente: `http://<IP>/api/getData?path=player:volume&roles=value` |
| Entidades indisponíveis | O app Klipsch pode estar consultando simultaneamente — feche-o |
| Atualizações lentas | Aumente o intervalo de consulta em Opções |
| Comandos além de volume/mudo falham | Verifique o sensor de diagnóstico **MAC de assinatura**. Se ele não mostrar um MAC resolvido (ou mostrar um errado), informe o MAC da soundbar como **MAC do dispositivo** em Opções |
| Integração não carrega | Verifique os logs do HA por erros de importação. Requer HA 2024.11+ |
| Subwoofer ou surround sem fio perde a conexão | Ative **Monitorizar caixas sem fios** em Opções e depois abra o dispositivo da caixa sob a soundbar: o sensor **Conectado** fica desligado enquanto o link está caído, e o histórico mostra quando ele caiu. A soundbar então informa o slot como vazio, ou seja, esta é a visão que a soundbar tem do link sem fio. Uma caixa cuja placa trava enquanto o rádio continua ligado (sem som) ainda aparece como conectada; o atributo `mcu_responding` mostra se a placa respondeu na última leitura (pressione **Ler caixas sem fios** para verificar). Desligar e religar a caixa por uma tomada inteligente costuma resolver |
| Logo invisível no tema escuro | Atualize para v2.5.19+ e reinicie o HA. O ícone para o tema escuro vem com a integração e requer HA 2026.3+; versões anteriores mostram o ícone preto do site de marcas do HA |

## Limitações conhecidas

- Uma soundbar por entrada de integração (adicione várias separadamente)
- Sem gerenciamento de multi-room / grupos surround sem fio (use Klipsch Connect Plus)
- O controle usa apenas a API HTTP nativa, não os protocolos Cast ou AirPlay. Google Cast é uma entrada selecionável (inicie a reprodução por um app com Cast); AirPlay não está na lista de entradas do dispositivo, por isso não é oferecido como fonte (transmitir para a soundbar a partir de um dispositivo Apple não é afetado)
- A configuração inicial deve ser concluída **por completo** no app oficial Klipsch Connect Plus — todo o processo pelo menos uma vez (isso provisiona a credencial de escrita do firmware de 2026)

## Segurança

Política de segurança e boas práticas em [SECURITY.md](../SECURITY.md).

**Aviso de segurança de rede:** a soundbar comunica por HTTP simples e a sua API local está praticamente sem autenticação na LAN. Firmware antigo não exigia autenticação nenhuma; o firmware de 2026 (`1.1.3.x`) assina a maioria das escritas (`HMAC_SHA256_AES256`), mas isto **não é uma fronteira de segurança real** — a credencial é derivada do próprio MAC do dispositivo (que ele divulga sem autenticação) mais uma constante fixa em toda a linha de produtos, por isso qualquer host na rede pode forjá-la. As leituras estão sempre abertas. **Mantenha a soundbar num segmento de rede confiável / isolado.** Análise completa no [relatório de avaliação de segurança](SECURITY_ASSESSMENT_CORE_300.md) (secção 12).

## Resultados dos testes

[![pytest, Home Assistant atual](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest, Home Assistant mais antigo suportado](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![CI local assinada](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

Todos os testes rodam na máquina do mantenedor, não no GitHub. Os cinco primeiros selos mostram os resultados dessa execução local assinada para o commit verificado mais recente em `main` (o selo *Signed local CI* mostra o SHA curto e a data dele). O GitHub só os grava depois de verificar a evidência assinada. *Verify signed local CI* é essa verificação no GitHub. *HACS validation* é a verificação do repositório pelo HACS, que roda no GitHub.

Você mesmo pode verificar a evidência (Python 3.11 ou mais recente, git, OpenSSH):

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` contém a chave pública de assinatura do mantenedor. Compare-a com as chaves SSH de assinatura que o GitHub lista para o mantenedor: `curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`. Detalhes em [TESTING.md](TESTING.md#test-result-badges) (em inglês).

## Colaboradores

Obrigado a todos que relatam problemas e enviam correções:

- **Kevin Jilissen** ([@Kevinjil](https://github.com/Kevinjil)) — descobriu que o volume da soundbar vai de 0 a 50, não de 0 a 100, e corrigiu a conversão ([#22](https://github.com/ilia-ae/klipsch_flexus/issues/22), [#23](https://github.com/ilia-ae/klipsch_flexus/pull/23))
- **G Johansson** ([@gjohansson-ST](https://github.com/gjohansson-ST)) — substituiu o estado `STANDBY` removido do media player para que a integração continue funcionando no Home Assistant 2026.12+ ([#25](https://github.com/ilia-ae/klipsch_flexus/pull/25))

Veja a [lista completa de colaboradores](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors).

## Contribuir e suporte

- **Dúvidas e ideias**: [GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions). O que incluir: [SUPPORT.md](../SUPPORT.md).
- **Bugs**: abra uma [issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose) com o formulário de bug e anexe os diagnósticos.
- **Problemas de segurança**: relate-os em privado, veja [SECURITY.md](../SECURITY.md).
- **Pull requests** são bem-vindos. [CONTRIBUTING.md](../CONTRIBUTING.md) explica como testar a sua alteração e como o mantenedor a verifica. [TESTING.md](TESTING.md) descreve os testes e a CI local assinada.
- Todos os participantes seguem o [Código de Conduta](../CODE_OF_CONDUCT.md).

## Licença

MIT — ver [LICENSE](../LICENSE).
