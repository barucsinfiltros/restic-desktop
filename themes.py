"""
Theme management module for Restic Manager
Contains all theme definitions and application logic
"""

import qdarkstyle
from qdarkstyle.light.palette import LightPalette


def apply_theme(app, settings_manager, theme: str):
    """
    Apply a theme to the application.
    
    Args:
        app: QApplication instance
        settings_manager: Settings manager instance
        theme: Theme name to apply
    """
    # Update the theme setting first
    settings_manager.set("theme", theme)
    
    if theme == "dark":
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
    elif theme == "dark-cyan":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #001f2f;
            color: #00ffff;
        }

        QPushButton {
            background-color: #003344;
            color: #00ffff;
        }

        QPushButton:hover {
            background-color: #035a70;
            color: #00ffff;
        }

        QPushButton:checked {
            background-color: #00667a;
            color: #ffffff;
            border: 2px solid #00ffff;
        }

        QPushButton:focus {
            outline: none;
            border: 1px solid #00ffff;
        }

        QPushButton:pressed {
            background-color: #022e3a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "dark-navy":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #12233d;
            color: #dadfe6;
        }

        QPushButton {
            background-color: #1f3a5c;
            color: #dadfe6;
        }

        QPushButton:hover {
            background-color: #2d4a70;
            border: 1px solid #70a0ff;
            color: #ffffff;
        }

        QPushButton:checked {
            background-color: #3a5a80;
            border: 2px solid #70a0ff;
            color: #ffffff;
        }

        QPushButton:focus {
            border: 1px solid #70a0ff;
        }

        QPushButton:pressed {
            background-color: #1a2e4a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "dark-green":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #0c2b29;
            color: #dadfe6;
        }

        QPushButton {
            background-color: #145c54;
            color: #dadfe6;
        }

        QPushButton:hover {
            background-color: #1f7a6d;
            border: 1px solid #88ffcc;
            color: #ffffff;
        }

        QPushButton:checked {
            background-color: #258b7d;
            border: 2px solid #88ffcc;
            color: #ffffff;
        }

        QPushButton:focus {
            border: 1px solid #88ffcc;
        }

        QPushButton:pressed {
            background-color: #0f3f3a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "light-green":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
        stylesheet += """
        QWidget {
            background-color: #d5f2e6;
            color: #222423;
        }

        QPushButton {
            background-color: #9fcfbc;
            color: #222423;
        }

        QPushButton:hover {
            background-color: #5c9c87;
            border: 1px solid #3c7a69;
            color: #ffffff;
        }

        QPushButton:checked {
            background-color: #4a8a75;
            border: 2px solid #00cc99;
            color: #ffffff;
        }

        QPushButton:focus {
            border: 1px solid #00cc99;
        }

        QPushButton:pressed {
            background-color: #497d6b;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "dark-purple":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1c0f2f;
            color: #d4c6f0;
        }
        QPushButton {
            background-color: #2e1a4f;
            color: #d4c6f0;
            border: 1px solid #835fdd;
        }
        QPushButton:hover {
            background-color: #3b2060;
            border: 1px solid #a07bff;
        }
        QPushButton:checked {
            background-color: #472570;
            border: 2px solid #a07bff;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "solarized-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #002b36;
            color: #93a1a1;
        }
        QPushButton {
            background-color: #073642;
            color: #93a1a1;
            border: 1px solid #586e75;
        }
        QPushButton:hover {
            background-color: #0c3b49;
            border: 1px solid #839496;
        }
        QPushButton:checked {
            background-color: #104650;
            border: 2px solid #839496;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)
        
    elif theme == "light-blue":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
        stylesheet += """
        QWidget {
            background-color: #e7f0fb;
            color: #1a2b3c;
        }
        QPushButton {
            background-color: #b6d8f2;
            color: #1a2b3c;
            border: 1px solid #5a9ecf;
        }
        QPushButton:hover {
            background-color: #a0cfee;
            border: 1px solid #397ebd;
        }
        QPushButton:checked {
            background-color: #8fc6ea;
            border: 2px solid #397ebd;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "monokai-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #272822;
            color: #f8f8f2;
        }
        QPushButton {
            background-color: #49483e;
            color: #f8f8f2;
            border: 1px solid #a6e22e;
        }
        QPushButton:hover {
            background-color: #5a594d;
            border: 1px solid #a6e22e;
        }
        QPushButton:checked {
            background-color: #6b6a5c;
            border: 2px solid #a6e22e;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "dark-indigo":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1a1b3a;
            color: #c3c8f0;
        }
        QPushButton {
            background-color: #2e2f5e;
            color: #c3c8f0;
        }
        QPushButton:hover {
            background-color: #44468f;
            color: #ffffff;
            border: 1px solid #5c5fd2;
        }
        QPushButton:checked {
            background-color: #5052a0;
            border: 2px solid #5c5fd2;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)
        
    elif theme == "dark-magenta":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #2a0a2a;
            color: #f2d9f7;
        }
        QPushButton {
            background-color: #4c1a4c;
            color: #f2d9f7;
        }
        QPushButton:hover {
            background-color: #6e2a6e;
            color: #ffffff;
            border: 1px solid #cc66cc;
        }
        QPushButton:checked {
            background-color: #7d357d;
            border: 2px solid #cc66cc;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "sunset-orange":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
        stylesheet += """
        QWidget {
            background-color: #fff3e6;
            color: #552200;
        }
        QPushButton {
            background-color: #ff884d;
            color: #fff3e6;
        }
        QPushButton:hover {
            background-color: #e67300;
            color: #ffffff;
            border: 1px solid #cc5200;
        }
        QPushButton:checked {
            background-color: #d66500;
            border: 2px solid #cc5200;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "forest-moss":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1c2d24;
            color: #cfe9cc;
        }
        QPushButton {
            background-color: #355e3b;
            color: #cfe9cc;
        }
        QPushButton:hover {
            background-color: #4b8b5c;
            color: #ffffff;
            border: 1px solid #6bbf59;
        }
        QPushButton:checked {
            background-color: #5a9a6b;
            border: 2px solid #6bbf59;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "cool-grey":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #2e2e38;
            color: #dcdfe6;
        }
        QPushButton {
            background-color: #1e2a3a;
            color: #e1e5e9;
            border: 1px solid #3a4f66;
        }
        QPushButton:hover {
            background-color: #2a3847;
            border: 1px solid #5a8fb4;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #3d4e63;
            border: 2px solid #8db9d1;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #152028;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "pure-black":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #000000;
            color: #ffffff;
        }
        QPushButton {
            background-color: #333333;
            color: #ffffff;
            border: 1px solid #666666;
        }
        QPushButton:hover {
            background-color: #444444;
            border: 1px solid #888888;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #555555;
            border: 2px solid #ffffff;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #222222;
        }
        QScrollArea {
            background-color: #000000;
        }
        QFrame {
            background-color: #000000;
            border: 1px solid #333333;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "midnight-blue":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #0d1421;
            color: #e1e5e9;
        }
        QPushButton {
            background-color: #1e2a3a;
            color: #e1e5e9;
            border: 1px solid #3a4f66;
        }
        QPushButton:hover {
            background-color: #2a3847;
            border: 1px solid #5a8fb4;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #3d4e63;
            border: 2px solid #8db9d1;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #152028;
        }
        """
        app.setStyleSheet(stylesheet)
            
    elif theme == "cyberpunk-neon":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #0a0a0a;
            color: #00f5ff;
        }
        QPushButton {
            background-color: #1a0a1a;
            color: #00f5ff;
            border: 1px solid #ff006e;
        }
        QPushButton:hover {
            background-color: #2a1a2a;
            border: 1px solid #8338ec;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #3a2a3a;
            border: 2px solid #ff006e;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #1a0a1a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "github-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #0d1117;
            color: #f0f6fc;
        }
        QPushButton {
            background-color: #21262d;
            color: #f0f6fc;
            border: 1px solid #30363d;
        }
        QPushButton:hover {
            background-color: #30363d;
            border: 1px solid #58a6ff;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #388bfd;
            border: 2px solid #58a6ff;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #161b22;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "vscode-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1e1e1e;
            color: #d4d4d4;
        }
        QPushButton {
            background-color: #3c3c3c;
            color: #d4d4d4;
            border: 1px solid #5a5a5a;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            border: 1px solid #9cdcfe;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #0e639c;
            border: 2px solid #9cdcfe;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "material-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #212121;
            color: #ffffff;
        }
        QPushButton {
            background-color: #424242;
            color: #ffffff;
            border: 1px solid #616161;
        }
        QPushButton:hover {
            background-color: #616161;
            border: 1px solid #9575cd;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #9575cd;
            border: 2px solid #b39ddb;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #1a1a1a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "dracula":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #282a36;
            color: #f8f8f2;
        }
        QPushButton {
            background-color: #44475a;
            color: #f8f8f2;
            border: 1px solid #6272a4;
        }
        QPushButton:hover {
            background-color: #6272a4;
            border: 1px solid #50fa7b;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #bd93f9;
            border: 2px solid #ff79c6;
            color: #282a36;
        }
        QPushButton:pressed {
            background-color: #21222c;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "nord-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #2e3440;
            color: #eceff4;
        }
        QPushButton {
            background-color: #3b4252;
            color: #eceff4;
            border: 1px solid #434c5e;
        }
        QPushButton:hover {
            background-color: #434c5e;
            border: 1px solid #88c0d0;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #5e81ac;
            border: 2px solid #81a1c1;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #242831;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "amoled-black":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #000000;
            color: #ffffff;
        }
        QPushButton {
            background-color: #111111;
            color: #ffffff;
            border: 1px solid #333333;
        }
        QPushButton:hover {
            background-color: #222222;
            border: 1px solid #bb86fc;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #333333;
            border: 2px solid #03dac6;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #0a0a0a;
        }
        QScrollArea {
            background-color: #000000;
        }
        QFrame {
            background-color: #000000;
            border: 1px solid #111111;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "matrix-green":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #000800;
            color: #00ff00;
        }
        QPushButton {
            background-color: #001100;
            color: #00ff00;
            border: 1px solid #00aa00;
        }
        QPushButton:hover {
            background-color: #002200;
            border: 1px solid #00ff00;
            color: #00ff00;
        }
        QPushButton:checked {
            background-color: #003300;
            border: 2px solid #00ff00;
            color: #000000;
        }
        QPushButton:pressed {
            background-color: #000800;
        }
        QScrollArea {
            background-color: #000000;
        }
        QFrame {
            background-color: #000000;
            border: 1px solid #001100;
        }
        """
        app.setStyleSheet(stylesheet)
    
    # Modern popular themes (2024-2026)
    elif theme == "tokyo-night":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1a1b26;
            color: #c0caf5;
        }
        QPushButton {
            background-color: #24283b;
            color: #c0caf5;
            border: 1px solid #414868;
        }
        QPushButton:hover {
            background-color: #292e42;
            border: 1px solid #7aa2f7;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #3d59a1;
            border: 2px solid #7aa2f7;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #1f2335;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "catppuccin-mocha":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        QPushButton {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
        }
        QPushButton:hover {
            background-color: #45475a;
            border: 1px solid #89b4fa;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #89b4fa;
            border: 2px solid #b4befe;
            color: #1e1e2e;
        }
        QPushButton:pressed {
            background-color: #181825;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "gruvbox-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #282828;
            color: #ebdbb2;
        }
        QPushButton {
            background-color: #3c3836;
            color: #ebdbb2;
            border: 1px solid #504945;
        }
        QPushButton:hover {
            background-color: #504945;
            border: 1px solid #b8bb26;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #b8bb26;
            border: 2px solid #fabd2f;
            color: #282828;
        }
        QPushButton:pressed {
            background-color: #1d2021;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "one-dark":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #282c34;
            color: #abb2bf;
        }
        QPushButton {
            background-color: #3e4451;
            color: #abb2bf;
            border: 1px solid #4b5263;
        }
        QPushButton:hover {
            background-color: #4b5263;
            border: 1px solid #61afef;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #61afef;
            border: 2px solid #528bff;
            color: #282c34;
        }
        QPushButton:pressed {
            background-color: #21252b;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "rose-pine":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #191724;
            color: #e0def4;
        }
        QPushButton {
            background-color: #1f1d2e;
            color: #e0def4;
            border: 1px solid #26233a;
        }
        QPushButton:hover {
            background-color: #26233a;
            border: 1px solid #c4a7e7;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #c4a7e7;
            border: 2px solid #ebbcba;
            color: #191724;
        }
        QPushButton:pressed {
            background-color: #151320;
        }
        """
        app.setStyleSheet(stylesheet)
              
    elif theme == "everforest":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #2d353b;
            color: #d3c6aa;
        }
        QPushButton {
            background-color: #343f44;
            color: #d3c6aa;
            border: 1px solid #475258;
        }
        QPushButton:hover {
            background-color: #475258;
            border: 1px solid #a7c080;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #a7c080;
            border: 2px solid #dbbc7f;
            color: #2d353b;
        }
        QPushButton:pressed {
            background-color: #272e33;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "kanagawa":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1f1f28;
            color: #dcd7ba;
        }
        QPushButton {
            background-color: #2a2a37;
            color: #dcd7ba;
            border: 1px solid #363646;
        }
        QPushButton:hover {
            background-color: #363646;
            border: 1px solid #7e9cd8;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #7e9cd8;
            border: 2px solid #7fb4ca;
            color: #1f1f28;
        }
        QPushButton:pressed {
            background-color: #16161d;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "night-owl":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #011627;
            color: #d6deeb;
        }
        QPushButton {
            background-color: #0b2942;
            color: #d6deeb;
            border: 1px solid #1d3b53;
        }
        QPushButton:hover {
            background-color: #1d3b53;
            border: 1px solid #82aaff;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #82aaff;
            border: 2px solid #c792ea;
            color: #011627;
        }
        QPushButton:pressed {
            background-color: #001d3a;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "palenight":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #292d3e;
            color: #a6accd;
        }
        QPushButton {
            background-color: #34324a;
            color: #a6accd;
            border: 1px solid #444267;
        }
        QPushButton:hover {
            background-color: #444267;
            border: 1px solid #82aaff;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #82aaff;
            border: 2px solid #c792ea;
            color: #292d3e;
        }
        QPushButton:pressed {
            background-color: #1f2233;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "arctic":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #2e3440;
            color: #d8dee9;
        }
        QPushButton {
            background-color: #3b4252;
            color: #d8dee9;
            border: 1px solid #4c566a;
        }
        QPushButton:hover {
            background-color: #4c566a;
            border: 1px solid #88c0d0;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #88c0d0;
            border: 2px solid #8fbcbb;
            color: #2e3440;
        }
        QPushButton:pressed {
            background-color: #2a3040;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "horizon":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #1c1e26;
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #232530;
            color: #e0e0e0;
            border: 1px solid #2e303e;
        }
        QPushButton:hover {
            background-color: #2e303e;
            border: 1px solid #fab795;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #f43e5c;
            border: 2px solid #fab795;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #16161c;
        }
        """
        app.setStyleSheet(stylesheet)

    elif theme == "moonlight":
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6')
        stylesheet += """
        QWidget {
            background-color: #212337;
            color: #c8d3f5;
        }
        QPushButton {
            background-color: #2f334d;
            color: #c8d3f5;
            border: 1px solid #3e4269;
        }
        QPushButton:hover {
            background-color: #3e4269;
            border: 1px solid #82aaff;
            color: #ffffff;
        }
        QPushButton:checked {
            background-color: #82aaff;
            border: 2px solid #c099ff;
            color: #212337;
        }
        QPushButton:pressed {
            background-color: #1b1e2e;
        }
        """
        app.setStyleSheet(stylesheet)

    else:
        # Light theme
        stylesheet = qdarkstyle.load_stylesheet(qt_api='pyqt6', palette=LightPalette)
        stylesheet += """
        QPushButton:checked {
            background-color: #007acc;
            border: 2px solid #005a9e;
            color: #ffffff;
        }
        """
        app.setStyleSheet(stylesheet)
