from flask import Blueprint, jsonify, current_app
from bson import ObjectId
from datetime import datetime





conversation_bp = Blueprint('conversation_bp', __name__)

@conversation_bp.route('/test')
def test_route():
    return jsonify(message="Conversation routes working!"), 200

@conversation_bp.route('/conversations', methods=['GET'])
def get_conversations():
    conversations = list(current_app.extensions['mongo']['conversations'].find(
        {},
        {'messages': 0}
    ).sort('updated_at', -1).limit(20))
    
    for conv in conversations:
        conv['_id'] = str(conv['_id'])
        conv['created_at'] = conv['created_at']
        conv['updated_at'] = conv['updated_at']
        
    return jsonify(conversations)

@conversation_bp.route('/conversation/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    try:
        conversation = current_app.extensions['mongo']['conversations'].find_one(
            {'_id': ObjectId(conversation_id)}
        )
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        conversation['_id'] = str(conversation['_id'])
        return jsonify(conversation)
    except:
        return jsonify({'error': 'Invalid conversation ID'}), 400

@conversation_bp.route('/conversation/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    try:
        result = current_app.extensions['mongo']['conversations'].delete_one(
            {'_id': ObjectId(conversation_id)}
        )
        if result.deleted_count == 0:
            return jsonify({'error': 'Conversation not found'}), 404
        return jsonify({'status': 'success'})
    except:
        return jsonify({'error': 'Invalid conversation ID'}), 400