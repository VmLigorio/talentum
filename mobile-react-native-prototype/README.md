# Talentum — protótipo React Native

Este diretório contém a versão React Native em comparação funcional com o aplicativo Flutter. Ainda é um protótipo e não substitui o app Flutter para distribuição.

O protótipo mantém o mesmo backend do Talentum e demonstra, em React Native:

- login do cliente;
- persistência segura da sessão;
- desbloqueio opcional por biometria;
- resumo financeiro e notificações;
- visualização da carteira e do patrimônio;
- metas e plano de ação, com filtros e edição de metas respeitando as permissões da API;
- edição de itens patrimoniais quando autorizada pela API;
- visualização de documentos e aviso de renovação anual;
- download autenticado e compartilhamento de documentos pelo menu nativo do aparelho;
- relatórios publicados;
- perfil cadastral, edição de perfil financeiro autorizada e alteração de senha;
- preferências de notificações;
- questionário versionado de suitability, com confirmação dos dados financeiros, perguntas de seleção múltipla e sugestão de carteira por objetivo e risco;
- registro de aceite, recusa ou pedido de ajustes depois da aprovação do Advisor;
- histórico de notificações com filtros e opção de marcar como lidas;
- opção segura por aparelho para ocultar os valores exibidos;
- criação, edição e desativação de alertas de preço;
- tratamento básico de API indisponível e renovação de sessão.

## Instalação

    cd /home/vitor-ligorio/talentum/mobile-react-native-prototype
    npm install
    npm run typecheck
    npm test

Os testes locais simulam a rede e o armazenamento nativo para verificar renovação simultânea
de sessão, download autenticado, fluxos de suitability, falhas temporárias, logout durante
chamadas em andamento e carregamento parcial. Execute-os com Node.js 22 ou superior. A validação
de biometria e da interface no aparelho continua sendo necessária.

Quando uma seção não pode ser carregada, o app mostra um aviso nessa seção e permite tentar
novamente em **Atualizar dados**. Os demais módulos continuam acessíveis. Falhas de rede
preservam os tokens; uma sessão recusada pela API exige novo login. Se a API estiver
temporariamente indisponível, o app pode apresentar a última cópia carregada para esse cliente,
salva no armazenamento protegido do aparelho. O aviso permanece visível até atualizar os dados.

## Executar no celular Android

Confirme que a API está disponível na porta 8001 e que o celular está na mesma rede Wi-Fi.

    EXPO_PUBLIC_API_URL=http://192.168.1.2:8001 npx expo start

Leia o QR Code pelo Expo Go ou execute:

    npx expo start --android

Se o endereço IP do computador mudar, substitua 192.168.1.2 pelo IP atual.

Para um Android físico, o endereço precisa ser o IP da máquina na mesma rede Wi-Fi. No emulador Android, use:

    EXPO_PUBLIC_API_URL=http://10.0.2.2:8001 npx expo start

## Comparação com o Flutter

O protótipo RN já cobre os principais módulos de cliente existentes no Flutter e usa os mesmos endpoints. Para comparar:

1. Suba a API na porta 8001.
2. Abra o Flutter com um cliente de teste.
3. Abra este protótipo com o mesmo cliente.
4. Compare login, resumo, carteira, metas, documentos, suitability, alertas, notificações e perfil.
5. Verifique especialmente tempo de abertura, atualização dos dados, rolagem e resposta dos modais.

## Limites conhecidos antes de produção

- Upload e alteração cadastral continuam reservados ao Advisor; o cliente pode editar somente os módulos liberados pela permissão da API.
- Notificações push e assinatura de distribuição ainda não fazem parte deste protótipo local.
- A árvore usa Expo SDK 52 para facilitar o teste; antes de produção, atualize o SDK de forma controlada e rode uma auditoria de dependências. Não aplique `npm audit fix --force` sem revisar as mudanças de versão.
- A interface foi validada por TypeScript e testes automatizados locais, mas falta testar os fluxos em aparelhos Android e iOS; documentos são abertos pelo menu de compartilhamento do sistema, sem visualizador dentro do app.
