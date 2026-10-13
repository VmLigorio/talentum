import Cocoa
import FlutterMacOS

/// Define o encerramento e a restauração segura da aplicação macOS.
@main
class AppDelegate: FlutterAppDelegate {
  /// Encerra o aplicativo quando a última janela for fechada.
  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    return true
  }

  /// Permite que o macOS restaure o estado seguro das janelas do aplicativo.
  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }
}
