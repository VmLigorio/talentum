cmake_minimum_required(VERSION 3.14)
project(runner LANGUAGES CXX)

# Define o executável do aplicativo. Para renomeá-lo, altere BINARY_NAME no
# CMakeLists.txt de nível superior; mudar somente este arquivo quebra `flutter run`.
#
# Inclua aqui qualquer novo arquivo-fonte próprio do aplicativo.
add_executable(${BINARY_NAME} WIN32
  "flutter_window.cpp"
  "main.cpp"
  "utils.cpp"
  "win32_window.cpp"
  "${FLUTTER_MANAGED_DIR}/generated_plugin_registrant.cc"
  "Runner.rc"
  "runner.exe.manifest"
)

# Aplica as opções de compilação padrão; substitua-as se o aplicativo precisar de outras.
apply_standard_settings(${BINARY_NAME})

# Disponibiliza os componentes da versão do aplicativo ao código C++.
target_compile_definitions(${BINARY_NAME} PRIVATE "FLUTTER_VERSION=\"${FLUTTER_VERSION}\"")
target_compile_definitions(${BINARY_NAME} PRIVATE "FLUTTER_VERSION_MAJOR=${FLUTTER_VERSION_MAJOR}")
target_compile_definitions(${BINARY_NAME} PRIVATE "FLUTTER_VERSION_MINOR=${FLUTTER_VERSION_MINOR}")
target_compile_definitions(${BINARY_NAME} PRIVATE "FLUTTER_VERSION_PATCH=${FLUTTER_VERSION_PATCH}")
target_compile_definitions(${BINARY_NAME} PRIVATE "FLUTTER_VERSION_BUILD=${FLUTTER_VERSION_BUILD}")

# Desativa macros do Windows que entram em conflito com funções da biblioteca C++.
target_compile_definitions(${BINARY_NAME} PRIVATE "NOMINMAX")

# Vincula bibliotecas e diretórios de inclusão do Flutter e de dependências próprias.
target_link_libraries(${BINARY_NAME} PRIVATE flutter flutter_wrapper_app)
target_link_libraries(${BINARY_NAME} PRIVATE "dwmapi.lib")
target_include_directories(${BINARY_NAME} PRIVATE "${CMAKE_SOURCE_DIR}")

# Executa a etapa do Flutter que prepara os artefatos necessários à compilação.
add_dependencies(${BINARY_NAME} flutter_assemble)
