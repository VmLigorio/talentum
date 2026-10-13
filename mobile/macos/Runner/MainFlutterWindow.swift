import Cocoa
import FlutterMacOS

/// Hospeda o controller Flutter e registra plugins na janela principal do macOS.
class MainFlutterWindow: NSWindow {
  /// Conecta o controller Flutter à janela e registra seus plugins nativos.
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)

    // Associa ao mecanismo os plugins nativos antes de exibir a janela.
    RegisterGeneratedPlugins(registry: flutterViewController)

    super.awakeFromNib()
  }
}
