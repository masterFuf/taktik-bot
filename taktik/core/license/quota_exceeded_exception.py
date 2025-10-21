class QuotaExceededException(Exception):    
    def __init__(self, message: str = "Daily interaction quota reached"):
        self.message = message
        super().__init__(self.message)
