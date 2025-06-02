# engine.py
import glfw, math, sys
from OpenGL.GL import *
import Util as lu
from ObjModel import ObjModel
import magic

class View:
    keymap = {k: getattr(glfw, f"KEY_{k}") for k in "WASD SPACE".split()}
    mousemap = {"LEFT": glfw.MOUSE_BUTTON_LEFT, "RIGHT": glfw.MOUSE_BUTTON_RIGHT}
    def __init__(self):
        self.models, self.offsets = {}, {}
        self.camera, self.lighting = Camera(), Lighting()
        self.shader = None
        self.vertex_src = ObjModel.defaultVertexShader
        self.fragment_src = ObjModel.defaultFragmentShader
        self.fragment_file = 'fragmentShader.glsl'
        self.reload_timer, self.mouse_pos = 1.0, None
        self.width = self.height = None

    def init_resources(self):
        def load(name, count=1): return [ObjModel(f"model/{name}.obj") for _ in range(count)]
        self.models = {
            "board": ObjModel("model/board.obj"),
            "highlight": ObjModel("model/highlight.obj"),
            "whiteKing": ObjModel("model/whiteKing.obj"),
            "blackKing": ObjModel("model/blackKing.obj"),
            "whiteQueen": ObjModel("model/whiteQueen.obj"),
            "blackQueen": ObjModel("model/blackQueen.obj"),
            "whitePawn": load("whitePawn", 8), "blackPawn": load("blackPawn", 8),
            "whiteBishop": load("whiteBishop", 2), "blackBishop": load("blackBishop", 2),
            "whiteKnight": load("whiteKnight", 2), "blackKnight": load("blackKnight", 2),
            "whiteRook": load("whiteRook", 2), "blackRook": load("blackRook", 2),
        }
        center, size = self.models["board"].centre, lu.length(self.models["board"].centre - self.models["board"].aabbMin)
        self.camera.target, self.camera.distance = center, size * 3.1
        self.lighting.lightDistance = size * 1.3
        self.shader = build_shader(self.vertex_src, self.fragment_src)
        self.reload_shader()
        def pos(row, cols): return [[row, -7+1*i] for i in cols]
        self.offsets.update({
            "whiteKing": [7, -4], "blackKing": [0, -4],
            "whiteQueen": [7, -3], "blackQueen": [0, -3],
            "whitePawn": pos(6, range(8)), "blackPawn": pos(1, range(8)),
            "whiteBishop": [[7, -5], [7, -2]], "blackBishop": [[0, -5], [0, -2]],
            "whiteKnight": [[7, -6], [7, -1]], "blackKnight": [[0, -6], [0, -1]],
            "whiteRook": [[7, -7], [7, 0]], "blackRook": [[0, -7], [0, 0]],
            "highlight": [0, 0]
        })
        glEnable(GL_DEPTH_TEST); glEnable(GL_CULL_FACE)
        glEnable(GL_TEXTURE_CUBE_MAP_SEAMLESS); glEnable(GL_FRAMEBUFFER_SRGB)

    def rotate(self, angle): self.camera.yaw = (self.camera.yaw + angle) % 360

    def render(self, xOff, w, h):
        glViewport(xOff, 0, w, h)
        glClearColor(66/255, 179/255, 245/255, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        lrot = lu.Mat3(lu.make_rotation_y(math.radians(self.lighting.yaw))) @ lu.Mat3(lu.make_rotation_x(math.radians(self.lighting.pitch)))
        lpos = self.models["board"].centre + lrot @ lu.vec3(0, 0, self.lighting.lightDistance)
        eye = lu.Mat3(lu.make_rotation_y(math.radians(self.camera.yaw)) @ lu.make_rotation_x(-math.radians(self.camera.pitch))) @ [0, 0, self.camera.distance]
        w2v = magic.make_lookAt(eye, [0, self.camera.height, 0], [0, 1, 0])
        v2c = magic.make_perspective(45.0, w/h, 0.1, 1000.0)
        glUseProgram(self.shader)
        lu.setUniform(self.shader, "viewSpaceLightPosition", lu.transformPoint(w2v, lpos))
        lu.setUniform(self.shader, "lightColourAndIntensity", self.lighting.color)
        lu.setUniform(self.shader, "ambientLightColourAndIntensity", self.lighting.ambient)
        lu.setUniform(self.shader, "viewToWorldRotationTransform", lu.inverse(lu.Mat3(w2v)))
        def draw_piece(name, i=None):
            offset = self.offsets[name] if i is None else self.offsets[name][i]
            pos = lu.make_translation(-3.5 + offset[0], 0.46, 3.5 + offset[1])
            self.draw_model(v2c, w2v, pos, self.models[name] if i is None else self.models[name][i])
        for k in ["board", "whiteKing", "blackKing", "whiteQueen", "blackQueen"]: draw_piece(k)
        for i in range(8): draw_piece("whitePawn", i), draw_piece("blackPawn", i)
        for i in range(2):
            for k in ["whiteBishop", "blackBishop", "whiteKnight", "blackKnight", "whiteRook", "blackRook"]: draw_piece(k, i)
        hl = lu.make_translation(-3.5+self.offsets["highlight"][0], 0.46, 3.5-self.offsets["highlight"][1])
        self.draw_model(v2c, w2v, hl, self.models["highlight"])
        self.width, self.height = w, h

    def draw_model(self, v2c, w2v, m2w, model):
        m2v = w2v * m2w
        m2vn = lu.inverse(lu.transpose(lu.Mat3(m2v)))
        tfms = {"modelToClipTransform": v2c * m2v, "modelToViewTransform": m2v, "modelToViewNormalTransform": m2vn}
        glUseProgram(self.shader)
        model.render(self.shader, ObjModel.RF_Opaque, tfms)
        glEnable(GL_BLEND); glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        model.render(self.shader, ObjModel.RF_Transparent | ObjModel.RF_AlphaTested, tfms)
        glDisable(GL_BLEND)

    def reload_shader(self):
        try:
            with open("vertexShader.glsl") as vs, open(self.fragment_file) as fs:
                vs_src, fs_src = vs.read(), fs.read()
                if vs_src != self.vertex_src or fs_src != self.fragment_src:
                    new_shader = build_shader(vs_src, fs_src)
                    if new_shader:
                        if self.shader: glDeleteProgram(self.shader)
                        self.shader = new_shader
                        print("Shader reloaded")
                    self.vertex_src, self.fragment_src = vs_src, fs_src
        except: pass

class Camera: 
    def __init__(self): self.yaw, self.pitch, self.height, self.distance = 270, 45, -1, 15

class Lighting:
    def __init__(self):
        self.yaw, self.pitch, self.lightDistance = 25, -30, 500
        self.color = lu.vec3(0.9, 0.9, 0.6)
        self.ambient = lu.vec3(0.1)

def build_shader(vs, fs):
    shader = lu.buildShader(vs, fs, ObjModel.getDefaultAttributeBindings())
    if shader:
        glUseProgram(shader)
        ObjModel.setDefaultUniformBindings(shader)
        glUseProgram(0)
    return shader

def init_glfw(title, w, h, cb):
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.SRGB_CAPABLE, 1)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    window = glfw.create_window(w, h, title, None, None)
    if not window: glfw.terminate(); sys.exit(1)
    glfw.make_context_current(window)
    glEnable(GL_DEPTH_TEST); glDisable(GL_CULL_FACE)
    if cb: cb()
    return window
