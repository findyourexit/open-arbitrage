class Player:
    def __init__(self, name):
        self.name = name
        self.stash = []

    def stash_add(self, item, quantity):
        self.stash.append([item, quantity])

    def stash_remove(self, item, quantity):
        self.stash.remove([item, quantity])
