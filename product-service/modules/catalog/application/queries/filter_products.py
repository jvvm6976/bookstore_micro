class FilterProductsQuery:
    def __init__(self, repository):
        self.repository = repository

    def execute(self, params):
        return self.repository.filter(params)
