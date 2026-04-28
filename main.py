import pygame

from engine.digital_twin import DigitalTwin
from ui.visual import Visual


def main():
    twin = DigitalTwin("config.json")
    visual = Visual(twin)

    clock = pygame.time.Clock()
    running = True
    paused = True

    while running:
        events = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused

        if not paused:
            twin.step()

        reset_requested = visual.update(events, paused=paused)

        if reset_requested:
            twin.reset()
            visual.sync_textboxes()
            paused = True

        clock.tick(20)

    pygame.quit()


if __name__ == "__main__":
    main()