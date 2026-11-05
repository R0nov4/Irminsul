// Teyvat Forecast — Quickshell entry point.
//
// Launch with:   qs -c teyvat-forecast
// IPC targets:   qs ipc call teyvat <function>
//
// Everything below uses Quickshell v0.3.x APIs only (verified against
// quickshell.org/docs/v0.3.0, cross-checked with v0.3.2):
//   IpcHandler (Quickshell.Io), Qt.quit(), Quickshell.execDetached().

import Quickshell
import Quickshell.Io
import QtQuick

Scope {
    WeatherPopup {}

    IpcHandler {
        target: "teyvat"

        function toggle(): void {
            PopupState.toggle()
        }

        function show(): void {
            PopupState.openPopup()
        }

        function hide(): void {
            PopupState.closePopup()
        }

        function search(): void {
            // open the popup with the city picker focused
            PopupState.openCitySearch()
        }

        function refresh(): void {
            // spawns the data-layer script; NO network I/O happens in QML
            WeatherData.requestRefresh()
        }

        function ping(): string {
            return "pong"
        }

        function quit(): void {
            Qt.quit()
        }
    }
}
