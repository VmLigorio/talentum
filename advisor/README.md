# Talentum Advisor

Painel web local para administradores e consultores.

## Executar

Com a API rodando em `127.0.0.1:8000`, inicie um servidor estático nesta pasta:

```bash
cd advisor
python3 -m http.server 8080
```

Abra <http://127.0.0.1:8080> e entre com um usuário `admin` ou `advisor` criado no backend.

O painel consome a mesma API do Mobile e permite consultar clientes, dashboard, permissões, publicar relatórios e pesquisar investimentos da B3 e do mercado internacional.

Na área “Pesquisar investimentos”, informe um ticker ou nome, escolha Brasil, Exterior ou ambos e
consulte preço, variação, volume, moeda, bolsa e tipo de ativo. O botão “Mais informações” abre
indicadores adicionais e, para FIIs, o resumo do informe mensal baseado em dados enviados à CVM,
além das referências oficiais. O painel exibe um aviso de que os dados são informativos e podem
ter atraso; a consulta é autorizada apenas para `admin` e `advisor`.

Na expansão do ativo, a seção “Análise histórica” permite selecionar 1 mês, 3 meses, 6 meses,
1 ano ou 5 anos. O gráfico mostra o retorno percentual acumulado do ativo comparado ao Ibovespa
ou ao S&P 500, conforme o mercado selecionado.

A mesma seção apresenta uma leitura descritiva do histórico: volatilidade anualizada, maior queda
desde um topo, volume médio e quantidade de observações. Essas métricas não constituem recomendação
ou classificação definitiva de risco.

É possível selecionar até três ativos e comparar os retornos históricos normalizados no mesmo gráfico,
com ranking do desempenho no período escolhido. O botão “Exportar análise” abre uma versão pronta para
impressão, que pode ser salva como PDF pelo navegador.

Ao iniciar uma nova pesquisa, a comparação anterior é limpa para evitar a exportação de dados antigos.
Se um dos provedores não responder, o painel preserva a comparação com os históricos disponíveis e informa
que o resultado é parcial.

O bloco “Monitorar um ativo” permite ao Advisor ou administrador criar um alerta de preço para um cliente,
escolhendo o mercado, preço-alvo e condição. A cotação é verificada ao atualizar as notificações; quando o
alvo é atingido, o alerta é marcado como disparado e o cliente e seu Advisor recebem uma notificação.
Alertas existentes também podem ser editados, pausados, reativados ou rearmados depois de disparados.

O bloco “Ativos monitorados” mantém uma lista de acompanhamento por cliente. O Advisor ou administrador
pode adicionar um ticker diretamente da busca, consultar a cotação atual e abrir novamente a pesquisa do ativo
sem precisar redigitar o símbolo.

Na área do cliente, a seção “Carteira de investimentos” permite registrar posições, preço médio, instituição
e observações. O painel calcula o valor atualizado, o resultado e a alocação por mercado/moeda sem misturar
BRL e USD.

O bloco “Desempenho da carteira” calcula o retorno histórico por posição, compara com o Ibovespa ou S&P 500,
aponta concentração e dados ausentes e permite imprimir um relatório da análise.

O provedor internacional está isolado por configuração no backend. Para operação comercial, valide
os direitos de uso e limites do fornecedor ou substitua-o por uma fonte licenciada.
