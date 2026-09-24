# Talentum — protótipo React Native

Este diretório é experimental e não substitui o aplicativo Flutter.

O protótipo mantém o mesmo backend do Talentum e demonstra:

- login do cliente;
- persistência segura da sessão;
- resumo financeiro;
- visualização da carteira;
- visualização de documentos;
- tratamento básico de API indisponível e renovação de sessão.

## Instalação

    cd /home/vitor-ligorio/talentum/mobile-react-native-prototype
    npm install
    npm run typecheck

## Executar no celular Android

Confirme que a API está disponível na porta 8001 e que o celular está na mesma rede Wi-Fi.

    EXPO_PUBLIC_API_URL=http://192.168.1.2:8001 npx expo start

Leia o QR Code pelo Expo Go ou execute:

    npx expo start --android

Se o endereço IP do computador mudar, substitua 192.168.1.2 pelo IP atual.

## Limites desta versão

Este protótipo ainda não implementa biometria, upload de documentos, suitability, alertas ou edição de carteira. A finalidade é comparar a experiência inicial e o custo técnico do React Native com a versão Flutter antes de uma eventual migração.
