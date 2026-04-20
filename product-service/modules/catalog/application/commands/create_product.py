class CreateProductCommand:
    def __init__(self, repository):
        self.repository = repository

    def execute(self, data):
        return self.repository.create(data)
