import Cocoa
import Foundation

// MARK: - Constants & Models

let DEFAULT_CELL_WIDTH: CGFloat = 192
let DEFAULT_CELL_HEIGHT: CGFloat = 208
let DEFAULT_COLUMNS = 8
let DEFAULT_ROWS = 9
let DEFAULT_UDP_PORT: UInt16 = 41738
let HUD_EXTRA_HEIGHT: CGFloat = 56.0

enum PetState: String, CaseIterable {
    case idle = "idle"          // Row 0
    case moveLeft = "move_left"  // Row 1
    case moveRight = "move_right"// Row 2
    case jump = "jump"          // Row 3
    case wave = "wave"          // Row 4
    case failed = "failed"      // Row 5
    case waiting = "waiting"    // Row 6
    case working = "working"    // Row 7
    case review = "review"      // Row 8

    var defaultRow: Int {
        switch self {
        case .idle: return 0
        case .moveLeft: return 1
        case .moveRight: return 2
        case .jump: return 3
        case .wave: return 4
        case .failed: return 5
        case .waiting: return 6
        case .working: return 7
        case .review: return 8
        }
    }
}

struct AnimationConfig {
    var row: Int
    var frames: Int = 8
    var fps: Double = 10.0
}

struct PetPackage {
    var id: String
    var name: String
    var directory: URL
    var spritesheetURL: URL
    var columns: Int = DEFAULT_COLUMNS
    var rows: Int = DEFAULT_ROWS
    var cellWidth: CGFloat = DEFAULT_CELL_WIDTH
    var cellHeight: CGFloat = DEFAULT_CELL_HEIGHT
    var defaultFps: Double = 10.0
    var animations: [PetState: AnimationConfig] = [:]
}

// MARK: - Asset Manager

class AssetManager {
    static let shared = AssetManager()

    var searchDirectories: [URL] = []

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        searchDirectories = [
            home.appendingPathComponent(".antigravity/pets"),
            home.appendingPathComponent(".codex/pets"),
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("assets/pets")
        ]
    }

    func discoverPets() -> [String: URL] {
        var result: [String: URL] = [:]
        for dir in searchDirectories {
            guard let contents = try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) else {
                continue
            }
            for item in contents {
                var isDir: ObjCBool = false
                if FileManager.default.fileExists(atPath: item.path, isDirectory: &isDir), isDir.boolValue {
                    let petJson = item.appendingPathComponent("pet.json")
                    let hasSpritesheet = ["spritesheet.webp", "spritesheet.png", "spritesheet.jpg"].contains {
                        FileManager.default.fileExists(atPath: item.appendingPathComponent($0).path)
                    }
                    if FileManager.default.fileExists(atPath: petJson.path) || hasSpritesheet {
                        if result[item.lastPathComponent] == nil {
                            result[item.lastPathComponent] = item
                        }
                    }
                }
            }
        }
        return result
    }

    func detectFrames(for img: NSImage, rows: Int, columns: Int, cellW: CGFloat, cellH: CGFloat) -> [Int: Int] {
        guard let tiff = img.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff) else { return [:] }

        var result: [Int: Int] = [:]
        let repW = rep.pixelsWide
        let repH = rep.pixelsHigh

        for row in 0..<rows {
            var lastNonEmptyCol = 0
            for col in (0..<columns).reversed() {
                let startX = Int(CGFloat(col) * cellW)
                let startY = Int(CGFloat(row) * cellH)

                var hasContent = false
                let midX = startX + Int(cellW) / 2
                for dy in stride(from: 20, to: Int(cellH) - 20, by: 10) {
                    let y = startY + dy
                    if midX < repW && y < repH, let c = rep.colorAt(x: midX, y: y), c.alphaComponent > 0.05 {
                        hasContent = true
                        break
                    }
                }
                if hasContent {
                    lastNonEmptyCol = col
                    break
                }
            }
            result[row] = max(1, lastNonEmptyCol + 1)
        }
        return result
    }

    func loadPet(from url: URL) -> PetPackage? {
        let petJsonURL = url.appendingPathComponent("pet.json")
        var name = url.lastPathComponent.capitalized
        var columns = DEFAULT_COLUMNS
        var rows = DEFAULT_ROWS
        var cellW = DEFAULT_CELL_WIDTH
        var cellH = DEFAULT_CELL_HEIGHT
        var defaultFps: Double = 10.0
        var anims: [PetState: AnimationConfig] = [:]

        if let data = try? Data(contentsOf: petJsonURL),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let n = json["name"] as? String { name = n }
            if let dn = json["displayName"] as? String { name = dn }
            if let f = json["fps"] as? Double { defaultFps = f }
            if let v = json["spriteVersionNumber"] as? Int, v == 2 {
                rows = 11
            }
            if let grid = json["grid"] as? [String: Any] {
                if let c = grid["columns"] as? Int { columns = c }
                if let r = grid["rows"] as? Int { rows = r }
                if let w = grid["cell_width"] as? Double { cellW = CGFloat(w) }
                if let h = grid["cell_height"] as? Double { cellH = CGFloat(h) }
            }
            if let rawAnims = json["animations"] as? [String: [String: Any]] {
                for state in PetState.allCases {
                    if let a = rawAnims[state.rawValue] {
                        let r = a["row"] as? Int ?? state.defaultRow
                        let f = a["frames"] as? Int ?? columns
                        let fps = a["fps"] as? Double ?? defaultFps
                        anims[state] = AnimationConfig(row: r, frames: f, fps: fps)
                    }
                }
            }
        }

        // Populate missing animation configs with defaults
        for state in PetState.allCases {
            if anims[state] == nil {
                anims[state] = AnimationConfig(row: state.defaultRow, frames: columns, fps: defaultFps)
            }
        }

        // Find spritesheet
        var spritesheet: URL? = nil
        let petJsonData = try? Data(contentsOf: petJsonURL)
        let petJsonDict = (try? JSONSerialization.jsonObject(with: petJsonData ?? Data())) as? [String: Any]
        if let explicit = petJsonDict?["spritesheetPath"] as? String {
            let candidate = url.appendingPathComponent(explicit)
            if FileManager.default.fileExists(atPath: candidate.path) {
                spritesheet = candidate
            }
        }
        if spritesheet == nil {
            for ext in ["spritesheet.webp", "spritesheet.png", "spritesheet.jpg"] {
                let candidate = url.appendingPathComponent(ext)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    spritesheet = candidate
                    break
                }
            }
        }

        guard let sheetURL = spritesheet else { return nil }

        // Derive true row count from actual image dimensions if possible
        if let img = NSImage(contentsOf: sheetURL) {
            let actualH = img.size.height
            if actualH > 0 && cellH > 0 {
                rows = max(1, Int(round(actualH / cellH)))
            }
            let actualW = img.size.width
            if actualW > 0 && cellW > 0 {
                columns = max(1, Int(round(actualW / cellW)))
            }

            let detected = detectFrames(for: img, rows: rows, columns: columns, cellW: cellW, cellH: cellH)
            for state in PetState.allCases {
                let row = anims[state]?.row ?? state.defaultRow
                if let count = detected[row] {
                    anims[state]?.frames = count
                }
            }
        }

        return PetPackage(
            id: url.lastPathComponent,
            name: name,
            directory: url,
            spritesheetURL: sheetURL,
            columns: columns,
            rows: rows,
            cellWidth: cellW,
            cellHeight: cellH,
            defaultFps: defaultFps,
            animations: anims
        )
    }
}

// MARK: - Pet Canvas View with Floating HUD

class PetCanvasView: NSView {
    var petPackage: PetPackage? {
        didSet {
            loadSpritesheet()
            updateTimer()
            needsDisplay = true
        }
    }

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        self.wantsLayer = true
        self.layerContentsRedrawPolicy = .onSetNeedsDisplay
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
        self.wantsLayer = true
        self.layerContentsRedrawPolicy = .onSetNeedsDisplay
    }

    var spritesheetImage: NSImage?
    var currentState: PetState = .idle
    var currentFrame: Int = 0
    var scaleFactor: CGFloat = 1.0
    var animationTimer: Timer?
    var revertTimer: Timer?

    // HUD Bubble properties
    var hudTitle: String? = nil
    var hudDetail: String? = nil
    var hudAlpha: CGFloat = 0.0
    var hudFadeTimer: Timer?

    private var dragStartWindowOrigin: NSPoint?
    private var dragStartMouseLocation: NSPoint?

    override var isFlipped: Bool { return false } // Cocoa native coordinates (bottom-left = 0,0)

    func loadSpritesheet() {
        guard let pet = petPackage else { return }
        spritesheetImage = NSImage(contentsOf: pet.spritesheetURL)
    }

    func setScale(_ scale: CGFloat) {
        scaleFactor = scale
        guard let pet = petPackage, let window = self.window else { return }
        let newWidth = max(pet.cellWidth * scaleFactor, 260.0 * scaleFactor)
        let newHeight = (pet.cellHeight * scaleFactor) + (HUD_EXTRA_HEIGHT * scaleFactor)

        var frame = window.frame
        let diffY = frame.height - newHeight
        frame.origin.y += diffY
        frame.size = NSSize(width: newWidth, height: newHeight)
        window.setFrame(frame, display: true, animate: true)
        needsDisplay = true
    }

    func setHUD(title: String?, detail: String?) {
        hudTitle = title
        hudDetail = detail
        hudAlpha = 1.0
        hudFadeTimer?.invalidate()
        hudFadeTimer = nil
        needsDisplay = true
    }

    func scheduleHUDFadeOut(delay: TimeInterval = 4.0) {
        hudFadeTimer?.invalidate()
        hudFadeTimer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { [weak self] _ in
            self?.hudAlpha = 0.0
            self?.needsDisplay = true
        }
    }

    func setState(_ newState: PetState, transientDuration: TimeInterval? = nil) {
        if currentState == newState && revertTimer == nil { return }
        revertTimer?.invalidate()
        revertTimer = nil

        currentState = newState
        currentFrame = 0
        updateTimer()
        needsDisplay = true

        if newState == .idle {
            scheduleHUDFadeOut(delay: 3.5)
        }

        if let duration = transientDuration {
            revertTimer = Timer.scheduledTimer(withTimeInterval: duration, repeats: false) { [weak self] _ in
                self?.setState(.idle)
            }
        }
    }

    func updateTimer() {
        animationTimer?.invalidate()
        let fps = petPackage?.animations[currentState]?.fps ?? 10.0
        let interval = max(0.02, 1.0 / fps)
        animationTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            guard let self = self, let pet = self.petPackage else { return }
            let maxFrames = pet.animations[self.currentState]?.frames ?? pet.columns
            self.currentFrame = (self.currentFrame + 1) % max(1, maxFrames)
            self.needsDisplay = true
        }
    }

    override func draw(_ dirtyRect: NSRect) {
        super.draw(dirtyRect)
        NSGraphicsContext.current?.cgContext.clear(dirtyRect)
        guard let img = spritesheetImage, let pet = petPackage else { return }

        // 1. Draw Pet Sprite at bottom of view
        let petW = pet.cellWidth * scaleFactor
        let petH = pet.cellHeight * scaleFactor
        let petX = (bounds.width - petW) / 2.0
        let petY: CGFloat = 0.0

        let anim = pet.animations[currentState] ?? AnimationConfig(row: currentState.defaultRow)
        let row = anim.row
        let maxFrames = anim.frames
        let col = currentFrame % max(1, maxFrames)

        // Spritesheet row 0 is at the top of the image file
        let sheetHeight = img.size.height
        let srcX = CGFloat(col) * pet.cellWidth
        let srcY = sheetHeight - CGFloat(row + 1) * pet.cellHeight

        let srcRect = NSRect(x: srcX, y: srcY, width: pet.cellWidth, height: pet.cellHeight)
        let destRect = NSRect(x: petX, y: petY, width: petW, height: petH)

        NSGraphicsContext.current?.imageInterpolation = .none
        img.draw(in: destRect, from: srcRect, operation: .sourceOver, fraction: 1.0)

        // 2. Draw Floating HUD Capsule Bubble directly above the pet
        if hudAlpha > 0.0 && (hudTitle != nil || hudDetail != nil) {
            drawHUD(petTopY: petY + petH)
        }
    }

    private func drawHUD(petTopY: CGFloat) {
        let titleText = hudTitle ?? ""
        let detailText = hudDetail ?? ""

        let titleFont = NSFont.systemFont(ofSize: 11.5, weight: .bold)
        let detailFont = NSFont.systemFont(ofSize: 9.5, weight: .regular)

        let titleAttrs: [NSAttributedString.Key: Any] = [
            .font: titleFont,
            .foregroundColor: NSColor(calibratedWhite: 1.0, alpha: 0.95 * hudAlpha)
        ]
        let detailAttrs: [NSAttributedString.Key: Any] = [
            .font: detailFont,
            .foregroundColor: NSColor(calibratedWhite: 0.82, alpha: 0.85 * hudAlpha)
        ]

        let titleSize = (titleText as NSString).size(withAttributes: titleAttrs)
        let detailSize = (detailText as NSString).size(withAttributes: detailAttrs)

        let contentWidth = max(titleSize.width, detailSize.width)
        let pillWidth = max(130.0, min(contentWidth + 28.0, bounds.width - 12.0))
        let pillHeight: CGFloat = 38.0
        let pillX = (bounds.width - pillWidth) / 2.0
        let pillY = petTopY + 4.0

        let pillRect = NSRect(x: pillX, y: pillY, width: pillWidth, height: pillHeight)
        let cornerRadius = pillHeight / 2.0
        let path = NSBezierPath(roundedRect: pillRect, xRadius: cornerRadius, yRadius: cornerRadius)

        // Translucent background
        NSColor(calibratedRed: 0.11, green: 0.12, blue: 0.15, alpha: 0.88 * hudAlpha).setFill()
        path.fill()

        // Subtle 1px border
        NSColor(calibratedWhite: 1.0, alpha: 0.16 * hudAlpha).setStroke()
        path.lineWidth = 1.0
        path.stroke()

        // Draw title (upper half)
        let titleX = pillX + (pillWidth - titleSize.width) / 2.0
        let titleY = pillY + pillHeight - titleSize.height - 5.0
        (titleText as NSString).draw(at: NSPoint(x: titleX, y: titleY), withAttributes: titleAttrs)

        // Draw detail (lower half)
        let detailX = pillX + (pillWidth - detailSize.width) / 2.0
        let detailY = pillY + 5.0
        (detailText as NSString).draw(at: NSPoint(x: detailX, y: detailY), withAttributes: detailAttrs)
    }

    // MARK: - Dragging & Mouse Interaction

    override func mouseDown(with event: NSEvent) {
        dragStartWindowOrigin = window?.frame.origin
        dragStartMouseLocation = NSEvent.mouseLocation
    }

    override func mouseDragged(with event: NSEvent) {
        guard let startOrigin = dragStartWindowOrigin,
              let startMouse = dragStartMouseLocation,
              let window = self.window else { return }

        let currentMouse = NSEvent.mouseLocation
        let dx = currentMouse.x - startMouse.x
        let dy = currentMouse.y - startMouse.y

        var newOrigin = startOrigin
        newOrigin.x += dx
        newOrigin.y += dy
        window.setFrameOrigin(newOrigin)

        if dx < -2 {
            setState(.moveLeft)
        } else if dx > 2 {
            setState(.moveRight)
        }
    }

    override func mouseUp(with event: NSEvent) {
        dragStartWindowOrigin = nil
        dragStartMouseLocation = nil
        if currentState == .moveLeft || currentState == .moveRight {
            setState(.idle)
        }
    }

    override func rightMouseDown(with event: NSEvent) {
        let menu = NSMenu(title: "Antigravity Pets")

        let titleItem = NSMenuItem(title: petPackage?.name ?? "Antigravity Pet", action: nil, keyEquivalent: "")
        titleItem.isEnabled = false
        menu.addItem(titleItem)
        menu.addItem(NSMenuItem.separator())

        // Pet selection submenu
        let petsSubmenu = NSMenu(title: "Select Pet")
        let availablePets = AssetManager.shared.discoverPets()
        for (petId, petURL) in availablePets.sorted(by: { $0.key < $1.key }) {
            let item = NSMenuItem(title: petId.capitalized, action: #selector(onSelectPet(_:)), keyEquivalent: "")
            item.target = self
            item.representedObject = petURL
            if petPackage?.id == petId {
                item.state = .on
            }
            petsSubmenu.addItem(item)
        }
        let selectPetItem = NSMenuItem(title: "Pets", action: nil, keyEquivalent: "")
        menu.setSubmenu(petsSubmenu, for: selectPetItem)
        menu.addItem(selectPetItem)

        // Scale submenu
        let scaleSubmenu = NSMenu(title: "Scale")
        for scale in [1.0, 1.5, 2.0] {
            let item = NSMenuItem(title: "\(scale)x", action: #selector(onSelectScale(_:)), keyEquivalent: "")
            item.target = self
            item.representedObject = scale
            if abs(scaleFactor - CGFloat(scale)) < 0.01 {
                item.state = .on
            }
            scaleSubmenu.addItem(item)
        }
        let scaleItem = NSMenuItem(title: "Scale", action: nil, keyEquivalent: "")
        menu.setSubmenu(scaleSubmenu, for: scaleItem)
        menu.addItem(scaleItem)

        menu.addItem(NSMenuItem.separator())

        let resetPosItem = NSMenuItem(title: "Reset Position", action: #selector(onResetPosition), keyEquivalent: "")
        resetPosItem.target = self
        menu.addItem(resetPosItem)

        menu.addItem(NSMenuItem.separator())

        let quitItem = NSMenuItem(title: "Quit", action: #selector(onQuit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        NSMenu.popUpContextMenu(menu, with: event, for: self)
    }

    @objc func onSelectPet(_ sender: NSMenuItem) {
        if let url = sender.representedObject as? URL,
           let pkg = AssetManager.shared.loadPet(from: url) {
            self.petPackage = pkg
            setScale(scaleFactor)
        }
    }

    @objc func onSelectScale(_ sender: NSMenuItem) {
        if let scale = sender.representedObject as? Double {
            setScale(CGFloat(scale))
        }
    }

    @objc func onResetPosition() {
        guard let window = self.window, let screen = window.screen ?? NSScreen.main else { return }
        let screenRect = screen.visibleFrame
        let x = screenRect.maxX - window.frame.width - 40
        let y = screenRect.minY + 40
        window.setFrameOrigin(NSPoint(x: x, y: y))
    }

    @objc func onQuit() {
        NSApp.terminate(nil)
    }
}

// MARK: - UDP Listener

class UDPListener {
    var socketFD: Int32 = -1
    var isRunning = false
    weak var canvasView: PetCanvasView?

    func start(port: UInt16 = DEFAULT_UDP_PORT) {
        socketFD = socket(AF_INET, SOCK_DGRAM, 0)
        guard socketFD >= 0 else {
            print("Failed creating UDP socket")
            return
        }

        var opt: Int32 = 1
        setsockopt(socketFD, SOL_SOCKET, SO_REUSEADDR, &opt, socklen_t(MemoryLayout<Int32>.size))

        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = port.bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")

        let bindResult = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sa in
                bind(socketFD, sa, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }

        guard bindResult == 0 else {
            print("Failed to bind UDP socket to port \(port)")
            close(socketFD)
            return
        }

        isRunning = true
        print("Antigravity Pets listening on UDP 127.0.0.1:\(port)")

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            var buffer = [UInt8](repeating: 0, count: 65535)

            while self.isRunning {
                let bytesRead = recv(self.socketFD, &buffer, buffer.count, 0)
                if bytesRead > 0 {
                    let data = Data(buffer[0..<bytesRead])
                    self.handlePacket(data: data)
                }
            }
        }
    }

    func stop() {
        isRunning = false
        if socketFD >= 0 {
            close(socketFD)
            socketFD = -1
        }
    }

    func handlePacket(data: Data) {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let event = json["event"] as? String else {
            return
        }

        let hasError = (json["error"] as? String) != nil && !((json["error"] as? String)?.isEmpty ?? true)
        let title = json["title"] as? String
        let detail = json["detail"] as? String

        DispatchQueue.main.async { [weak self] in
            guard let canvas = self?.canvasView else { return }

            canvas.setHUD(title: title ?? event, detail: detail ?? "")

            switch event {
            case "PreInvocation", "PreToolUse":
                canvas.setState(.working)
            case "PostToolUse":
                if hasError {
                    canvas.setState(.failed, transientDuration: 3.0)
                } else {
                    canvas.setState(.review)
                }
            case "PostInvocation":
                canvas.setState(.waiting)
            case "Stop":
                if hasError {
                    canvas.setState(.failed, transientDuration: 3.0)
                } else {
                    canvas.setState(.jump, transientDuration: 2.5)
                }
            default:
                break
            }
        }
    }
}

// MARK: - App Delegate & Main

class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var canvasView: PetCanvasView!
    var udpListener = UDPListener()

    func applicationDidFinishLaunching(_ notification: Notification) {
        let defaultWidth = max(DEFAULT_CELL_WIDTH, 260.0)
        let defaultHeight = DEFAULT_CELL_HEIGHT + HUD_EXTRA_HEIGHT

        // Position pet at bottom-right corner of screen
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        let initialRect = NSRect(
            x: screen.maxX - defaultWidth - 40,
            y: screen.minY + 40,
            width: defaultWidth,
            height: defaultHeight
        )

        window = NSWindow(
            contentRect: initialRect,
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.isOpaque = false
        window.backgroundColor = .clear
        window.level = .floating // Always on top
        window.hasShadow = false
        window.ignoresMouseEvents = false

        canvasView = PetCanvasView(frame: NSRect(x: 0, y: 0, width: defaultWidth, height: defaultHeight))

        // Discover and load default pet or first available pet
        let pets = AssetManager.shared.discoverPets()
        var selectedURL: URL? = nil
        if let defaultPet = pets["default"] {
            selectedURL = defaultPet
        } else if let firstPet = pets.values.first {
            selectedURL = firstPet
        }

        if let petURL = selectedURL, let pkg = AssetManager.shared.loadPet(from: petURL) {
            canvasView.petPackage = pkg
        }

        window.contentView = canvasView
        window.makeKeyAndOrderFront(nil)

        udpListener.canvasView = canvasView
        udpListener.start()
    }

    func applicationWillTerminate(_ notification: Notification) {
        udpListener.stop()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory) // Runs without dock icon for true lightweight companion
app.run()
