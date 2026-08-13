import Foundation
import Vision
import AppKit

func emit(_ obj: [String: Any], code: Int32 = 0) -> Never {
    if let data = try? JSONSerialization.data(withJSONObject: obj, options: []),
       let s = String(data: data, encoding: .utf8) {
        print(s)
    } else {
        print("{\"ok\":false,\"error\":\"JSON输出失败\"}")
    }
    exit(code)
}

guard CommandLine.arguments.count >= 2 else {
    emit(["ok": false, "error": "缺少图片路径"], code: 2)
}
let path = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: path) else {
    emit(["ok": false, "error": "无法读取图片"], code: 3)
}
var rect = NSRect(origin: .zero, size: image.size)
guard let cgImage = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) else {
    emit(["ok": false, "error": "无法解码图片"], code: 4)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
    let observations = request.results ?? []
    let lines = observations.compactMap { $0.topCandidates(1).first?.string }
    emit(["ok": true, "text": lines.joined(separator: "\n"), "lines": lines.count])
} catch {
    emit(["ok": false, "error": "Vision识别失败：\(error.localizedDescription)"], code: 5)
}