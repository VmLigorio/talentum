# Talentum MVP v0.1

## Objetivo

Entregar uma primeira versão utilizável para organizar o relacionamento com clientes, registrar patrimônio e metas, acompanhar planos de ação e disponibilizar relatórios.

## Incluído

### Cliente / Mobile

- login;
- perfil;
- dashboard;
- patrimônio;
- metas;
- relatórios;
- documentos autorizados;
- alertas e preferências de notificação;
- ocultação de valores;
- consulta do plano de ação.

### Advisor

- login administrativo;
- lista e detalhes de clientes;
- cadastro e edição de patrimônio;
- cadastro e edição de metas;
- envio de relatórios;
- plano de ação com prazos, prioridades e status;
- histórico básico;
- permissões por cliente.
- documentos compartilhados com validação de tipo e tamanho;
- alertas operacionais para prazos, metas e novos documentos;
- preferências de alertas por usuário.

### Pesquisa de investimentos / Desktop Advisor e Adm

- busca de ativos da B3 por ticker e nome;
- busca de ações, ETFs e outros ativos internacionais por ticker ou nome;
- preço, variação, volume, moeda, bolsa, tipo de ativo e horário da atualização;
- filtro por Brasil, exterior ou ambos;
- integração protegida no backend, sem expor tokens de provedores no navegador;
- aviso explícito de que dados de mercado podem ter atraso e não constituem recomendação.
- alertas de preço por ativo, com condição de alta ou baixa e notificação ao cliente/Advisor;
- gestão de alertas pelo cliente no Mobile e pelo Advisor/Admin no painel Desktop;
- lista de acompanhamento de ativos por cliente no painel Desktop.

## Fora do MVP

Open Finance, integração B3, cotação em tempo real, inteligência artificial, home broker, rebalanceamento automático, pagamentos, custódia, execução de ordens e gestão discricionária.

## Arquitetura

Um monólito modular em FastAPI com PostgreSQL. O Mobile (Flutter) e o Advisor (Next.js) consumirão a mesma API REST.

## Segurança mínima

Hash seguro de senhas, access token, refresh token, revogação de sessão, autorização por papel, isolamento por cliente, permissões aplicadas no backend, auditoria, proteção de secrets, validação de entrada e rate limiting no login.
