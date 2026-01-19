import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { api } from "../../scripts/api.js";

const VFX_FLOW_NODES = [
    "FlowLogin",
    "ProjectBrowser",
    "ShotBrowser",
    "TaskSelector",
    "PublishToFlow",
    "FilenameFromPipe",
    "AddNote"
];

// Deep teal color for Flow nodes (distinct from VFX Bridge anthracite)
const FLOW_COLOR = "#1a4a4a";
const FLOW_COLOR_DARK = "#0d2d2d";
const WATERMARK = "rgba(255,255,255,0.06)";

// Password field masking
function maskPasswordWidget(widget) {
    if (!widget || !widget.inputEl) return;
    widget.inputEl.type = "password";
    widget.inputEl.style.letterSpacing = "2px";
}

app.registerExtension({
    name: "vfx.flow.style",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (!VFX_FLOW_NODES.includes(nodeData.name)) return;
        
        // Flow Login - mask password and API key
        if (nodeData.name === "FlowLogin") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated ? onNodeCreated.apply(this, []) : undefined;
                
                // Find and mask sensitive widgets
                setTimeout(() => {
                    for (const widget of this.widgets || []) {
                        if (widget.name === "password" || widget.name === "api_key") {
                            maskPasswordWidget(widget);
                        }
                    }
                }, 100);
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
        }
        // Add text display for info outputs
        else if (["ProjectBrowser", "ShotBrowser", "TaskSelector", "PublishToFlow", "AddNote"].includes(nodeData.name)) {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated ? onNodeCreated.apply(this, []) : undefined;
                
                this.infoWidget = ComfyWidgets["STRING"](this, "info_display", ["STRING", { multiline: true }], app).widget;
                this.infoWidget.inputEl.readOnly = true;
                this.infoWidget.inputEl.style.opacity = 0.8;
                this.infoWidget.inputEl.style.fontSize = "11px";
                this.infoWidget.inputEl.style.minHeight = "60px";
                this.infoWidget.serializeValue = async () => "";
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
            
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                onExecuted ? onExecuted.apply(this, [message]) : undefined;
                
                // Find info in outputs
                if (message) {
                    const info = message.info || message.status || message.text;
                    if (info && this.infoWidget) {
                        this.infoWidget.value = Array.isArray(info) ? info[0] : info;
                    }
                }
            };
        } else {
            const origCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                if (origCreated) origCreated.apply(this, arguments);
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
        }
        
        // Watermark
        const origDraw = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function(ctx) {
            if (origDraw) origDraw.apply(this, arguments);
            ctx.save();
            ctx.font = "7px monospace";
            ctx.fillStyle = WATERMARK;
            ctx.textAlign = "right";
            ctx.fillText("vfx-flow", this.size[0] - 5, this.size[1] - 3);
            ctx.restore();
        };
    },
    
    async setup() {
        console.log("[VFX Flow] Styling loaded");
    }
});
