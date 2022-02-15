class Player:
    def __init__(self, name):
        self.name = name
        self.stash = []

    def stash_add(self, item, quantity):
        stash_item = self.stash_get(item)
        if stash_item is not None:
            stash_item[1] += quantity
        else:
            self.stash.append([item, quantity])

    def stash_remove(self, item, quantity):
        self.stash.remove([item, quantity])

    def stash_contains(self, item):
        for stash_item in self.stash:
            if stash_item.name == item.name:
                return True
        return False

    def stash_get(self, item):
        for stash_item in self.stash:
            if stash_item[0].name == item.name:
                return stash_item
        return None
