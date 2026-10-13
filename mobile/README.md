# Talentum Mobile

Aplicativo Flutter do cliente Talentum.

## Preparar o projeto

Na pasta `mobile`, gere os arquivos de plataforma com Flutter:

```bash
flutter create .
flutter pub get
```

O aplicativo mantém a sessão usando o refresh token em armazenamento seguro da plataforma; a senha não é armazenada no dispositivo.
O cache local de dados financeiros também usa armazenamento seguro. Preferências visuais não sensíveis permanecem no armazenamento comum.

O código já está preparado para consumir a API do Talentum. No Linux e no simulador iOS, usa `127.0.0.1`; em um emulador Android, usa `10.0.2.2` automaticamente. O endereço padrão usa a porta `8000`:

```bash
flutter run
```

No Android físico, `127.0.0.1` aponta para o próprio celular. Use o IP local do computador na mesma rede Wi-Fi e a porta publicada pela API. Por exemplo, para o Docker Compose local (`8001`):

```bash
flutter run --dart-define=API_URL=http://192.168.1.10:8001
```

Substitua `192.168.1.10` pelo IP atual do computador. O manifesto de depuração permite HTTP para esses testes locais; builds Release continuam exigindo HTTPS.

## Escopo do MVP Mobile

O aplicativo do cliente entrega o fluxo completo de uso do MVP:

- login persistente, renovação automática da sessão e troca de senha;
- painel com patrimônio total, fluxo mensal, distribuição, metas e ações;
- ocultação local de valores financeiros;
- consulta, criação, edição e remoção de patrimônio quando permitido;
- consulta, criação, edição, remoção, filtros e progresso de metas quando permitido;
- consulta do plano de ação definido pelo Advisor;
- leitura de relatórios publicados;
- envio e download de documentos autorizados, com limite de 10 MB;
- alertas persistentes, histórico, filtros, marcação como lido e preferências por categoria;
- perfil, perfil financeiro e permissões configuradas pelo Advisor.
- carteira consolidada com posições, preço médio, cotação atual, resultado e alocação por moeda.
- cache local da última sincronização para consulta durante indisponibilidade temporária da API.

Quando o cache estiver sendo exibido, o aplicativo identifica a tela como “Visualização offline”
e mostra a data da última atualização. O cache é removido ao sair da conta, trocar a senha ou
quando a sessão expira.

O endereço da API pode ser informado com `--dart-define=API_URL=...`. Para uma entrega real,
use HTTPS e um endereço acessível pelo dispositivo; o endereço `127.0.0.1` só funciona quando
a API está na própria máquina ou quando o emulador possui esse encaminhamento configurado.

### Gerar APK de teste pelo GitHub Actions

Na execução manual do workflow **Talentum security checks**, informe o campo `api_url`, como
`http://192.168.10.16:8001`. Para usar um endereço fixo nas compilações automáticas, configure
a variável de repositório `TALENTUM_API_URL` em **Settings → Secrets and variables → Actions → Variables**.
Se os dois estiverem vazios, o workflow mantém o endereço local atualmente usado nos testes.
O APK aparece no artefato `talentum-android-debug` por sete dias. A execução manual fica disponível
depois que o workflow estiver presente na branch padrão do repositório.

## Checklist de entrega

Com o Flutter instalado e habilitado no ambiente, execute na pasta `mobile`:

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --release --dart-define=API_URL=https://api.seu-dominio.com
```

Antes de publicar, substitua a assinatura de debug configurada no Android por uma assinatura
de produção e mantenha `API_URL` apontando para uma API HTTPS.
