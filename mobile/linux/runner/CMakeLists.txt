cmake_minimum_required(VERSION 3.13)
project(runner LANGUAGES CXX)

# Define o executável do aplicativo. Para renomeá-lo, altere BINARY_NAME no
# CMakeLists.txt de nível superior; mudar somente este arquivo quebra `flutter run`.
#
# Inclua aqui qualquer novo arquivo-fonte próprio do aplicativo.
add_executable(${BINARY_NAME}
  "main.cc"
  "my_application.cc"
  "${FLUTTER_MANAGED_DIR}/generated_plugin_registrant.cc"
)

# Aplica as opções de compilação padrão; substitua-as se o aplicativo precisar de outras.
apply_standard_settings(${BINARY_NAME})

# Disponibiliza o identificador do aplicativo como definição do pré-processador.
add_definitions(-DAPPLICATION_ID="${APPLICATION_ID}")

# Vincula o mecanismo Flutter, as bibliotecas GTK e dependências específicas do aplicativo.
target_link_libraries(${BINARY_NAME} PRIVATE flutter)
target_link_libraries(${BINARY_NAME} PRIVATE PkgConfig::GTK)

target_include_directories(${BINARY_NAME} PRIVATE "${CMAKE_SOURCE_DIR}")
