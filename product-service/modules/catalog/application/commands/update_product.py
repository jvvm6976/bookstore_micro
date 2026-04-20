class UpdateProductCommand:
    def __init__(self, repository):
        self.repository = repository

    def execute(self, product_id, data):
        return self.repository.update(product_id, data)
