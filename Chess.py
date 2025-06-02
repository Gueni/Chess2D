from OpenGL.GL import *
import imgui

import glfw
import sys

import magic
from time import sleep


from Chess.View import initGlFwAndResources, View, WIDTH, HEIGHT, WINDOW_TITLE
from Chess.Model import Game

def main():
    rotating = 0

    view = View()
    game = Game()

    if not glfw.init():
        sys.exit(1)

    window, impl = initGlFwAndResources(WINDOW_TITLE, WIDTH, HEIGHT, view)
    prevMouseX,prevMouseY = glfw.get_cursor_pos(window)

    hasClicked = False
    while game.is_playing() and not glfw.window_should_close(window):
        if rotating:
            view.rotate(9)
            rotating -= 1

        keyStateMap = {}
        for name,id in magic.g_glfwKeymap.items():
            keyStateMap[name] = glfw.get_key(window, id) == glfw.PRESS

        for name,id in magic.g_glfwMouseMap.items():
            keyStateMap[name] = glfw.get_mouse_button(window, id) == glfw.PRESS

        mouseX, mouseY = glfw.get_cursor_pos(window)
        view.mousePos = [mouseX,mouseY]

        if keyStateMap["SPACE"]:
            if game.get_focused() is not None:
                # second click
                position = tuple(view.offsets['highlight'])
                if position is not None:
                    x1, y1 = position
                    y2, x2 = game.get_focused_position()
                    model, i = game.get_model()
                    valid = game.move(y1, x1)
                    if valid:
                        if i is not None:
                            view.offsets[model][i][0] += x1-x2
                            view.offsets[model][i][1] += y2-y1
                        else:
                            view.offsets[model][0] += x1-x2
                            view.offsets[model][1] += y2-y1

                        rotating = 20
                        game.unfocus()
            else:
                x, y = tuple(view.offsets['highlight'])
                game.set_focused((y, x))
                print('Selected')

        if keyStateMap["W"]:
            if view.offsets['highlight'][0] > 0:
                view.offsets['highlight'][0] -= 1
        elif keyStateMap["A"]:
            if view.offsets['highlight'][1] > 0:
                view.offsets['highlight'][1] -= 1
        elif keyStateMap["S"]:
            if view.offsets['highlight'][0] < 7:
                view.offsets['highlight'][0] += 1
        elif keyStateMap["D"]:
            if view.offsets['highlight'][1] < 7:
                view.offsets['highlight'][1] += 1
        sleep(0.03)

        #print(game.get_focused())
        
        # Udpate 'game logic'
        if view.update:
            imIo = imgui.get_io()
            mouseDelta = [mouseX - prevMouseX,mouseY - prevMouseY]
            if imIo.want_capture_mouse:
                mouseDelta = [0,0]
            view.update(0, keyStateMap, mouseDelta)
        prevMouseX,prevMouseY = mouseX,mouseY

        width, height = glfw.get_framebuffer_size(window)
            
        view.renderFrame(0, width, height)
        #view.highlightPosition(mouseX, mouseY)
        glfw.swap_buffers(window)
        # Poll for and process events
        glfw.poll_events()
        impl.process_inputs()

    glfw.terminate()

if __name__ == '__main__':
  main()
