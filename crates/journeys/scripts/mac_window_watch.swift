import CoreGraphics
import Darwin
import Foundation

func write(_ value: String, to path: String) throws {
    try value.write(toFile: path, atomically: true, encoding: .utf8)
}

let args = CommandLine.arguments
if args.count != 4 {
    fputs("usage: mac_window_watch.swift READY_FILE PID_FILE RESULT_FILE\n", stderr)
    exit(2)
}
let readyPath = args[1]
let pidPath = args[2]
let resultPath = args[3]
try write("ready\n", to: readyPath)

while !FileManager.default.fileExists(atPath: pidPath) {
    usleep(1_000)
}
guard let pid = Int32(try String(contentsOfFile: pidPath, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)) else {
    fputs("invalid target process id\n", stderr)
    exit(2)
}

while true {
    let windows = CGWindowListCopyWindowInfo([.optionAll, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    let mapped = windows.contains { window in
        let ownerPID = (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value
        let layer = (window[kCGWindowLayer as String] as? NSNumber)?.intValue
        let alpha = (window[kCGWindowAlpha as String] as? NSNumber)?.doubleValue ?? 1.0
        let bounds = window[kCGWindowBounds as String] as? NSDictionary
        let width = (bounds?["Width"] as? NSNumber)?.doubleValue ?? 0.0
        let height = (bounds?["Height"] as? NSNumber)?.doubleValue ?? 0.0
        return ownerPID == pid && layer == 0 && alpha > 0.0 && width > 0.0 && height > 0.0
    }
    if mapped {
        var timestamp = timespec()
        clock_gettime(CLOCK_MONOTONIC, &timestamp)
        let monotonicNS = UInt64(timestamp.tv_sec) * 1_000_000_000 + UInt64(timestamp.tv_nsec)
        try write("\(monotonicNS)\n", to: resultPath)
        exit(0)
    }
    usleep(1_000)
}
