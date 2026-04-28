import pygame


class TextBox:
    def __init__(self, x, y, w, h, text="0"):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = str(text)
        self.active = False
        self.dirty = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
                self.dirty = True

            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                self.dirty = True

            elif event.key == pygame.K_MINUS:
                if not self.text.startswith("-"):
                    self.text = "-" + self.text
                    self.dirty = True

            elif event.key in (pygame.K_PERIOD, pygame.K_COMMA):
                if "." not in self.text:
                    self.text += "."
                    self.dirty = True

            elif event.unicode.isdigit():
                self.text += event.unicode
                self.dirty = True

    def value(self):
        try:
            return float(self.text)
        except ValueError:
            return None

    def consume_dirty(self):
        was_dirty = self.dirty
        self.dirty = False
        return was_dirty

    def set_text(self, value):
        self.text = str(value)
        self.dirty = False

    def draw(self, screen, font):
        pygame.draw.rect(screen, (20, 20, 20), self.rect)
        pygame.draw.rect(
            screen,
            (255, 255, 255) if self.active else (140, 140, 140),
            self.rect,
            2
        )

        txt = font.render(self.text, True, (255, 255, 255))
        screen.blit(txt, (self.rect.x + 5, self.rect.y + 4))


class Button:
    def __init__(self, x, y, w, h, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.clicked = False

    def handle_event(self, event):
        self.clicked = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.clicked = self.rect.collidepoint(event.pos)

    def draw(self, screen, font):
        pygame.draw.rect(screen, (70, 70, 70), self.rect, border_radius=6)
        pygame.draw.rect(screen, (220, 220, 220), self.rect, 2, border_radius=6)

        txt = font.render(self.label, True, (255, 255, 255))
        screen.blit(txt, (self.rect.x + 10, self.rect.y + 7))