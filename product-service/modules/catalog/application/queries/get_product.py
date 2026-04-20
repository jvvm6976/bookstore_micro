class GetProductQuery:
    def __init__(self, repository):
        self.repository = repository

    def execute(self, product_id):
        return self.repository.get(product_id)
