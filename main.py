# main.py
import glfw, sys
from OpenGL.GL import *
from time import sleep
from engine import View, init_glfw
from model import Game

def main():
    if not glfw.init(): sys.exit(1)
    view, game = View(), Game()
    window = init_glfw("Chess", 1280, 800, view.init_resources)
    prev_mouse = glfw.get_cursor_pos(window)
    rotating = 0

    while game.is_playing() and not glfw.window_should_close(window):
        rotating = max(rotating - 1, 0)
        if rotating: view.rotate(9)

        keys = {k: glfw.get_key(window, v) == glfw.PRESS for k, v in view.keymap.items()}
        keys.update({k: glfw.get_mouse_button(window, v) == glfw.PRESS for k, v in view.mousemap.items()})

        mx, my = glfw.get_cursor_pos(window)
        view.mouse_pos = [mx, my]

        if keys["SPACE"]:
            hl = tuple(view.offsets['highlight'])
            if game.get_focused():
                x1, y1 = hl
                y2, x2 = game.get_focused_position()
                model, i = game.get_model()
                if game.move(y1, x1):
                    offset = view.offsets[model][i] if i is not None else view.offsets[model]
                    offset[0] += x1 - x2
                    offset[1] += y2 - y1
                    game.unfocus()
                    rotating = 20
            else:
                x, y = hl
                game.set_focused((y, x))

        if keys["W"] and view.offsets['highlight'][0] > 0: view.offsets['highlight'][0] -= 1
        if keys["A"] and view.offsets['highlight'][1] > 0: view.offsets['highlight'][1] -= 1
        if keys["S"] and view.offsets['highlight'][0] < 7: view.offsets['highlight'][0] += 1
        if keys["D"] and view.offsets['highlight'][1] < 7: view.offsets['highlight'][1] += 1

        sleep(0.03)
        w, h = glfw.get_framebuffer_size(window)
        view.render(0, w, h)
        glfw.swap_buffers(window)
        glfw.poll_events()

    glfw.terminate()

if __name__ == "__main__":
    main()
