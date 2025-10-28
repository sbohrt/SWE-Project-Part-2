   # src/api/routes/crud.py
   # Implement endpoints for managing scored models
   @bp.route('/models', methods=['GET'])  # List models
   @bp.route('/models/<id>', methods=['GET'])  # Get specific model
   @bp.route('/models', methods=['POST'])  # Add model
   @bp.route('/models/<id>', methods=['PUT'])  # Update model
   @bp.route('/models/<id>', methods=['DELETE'])  # Delete model