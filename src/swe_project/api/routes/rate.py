# src/api/routes/rate.py
from flask import Blueprint, request, jsonify
import time
from swe_project.core.exec_pool import run_parallel
from swe_project.core.scoring import combine
from swe_project.metrics.base import registered
from swe_project.core.url_ctx import set_context

bp = Blueprint('rate', __name__)

@bp.route('/rate', methods=['POST'])
def rate_model():
    """Rate a model using Phase 1 metrics"""
    data = request.get_json()
    model_url = data.get('url')
    
    if not model_url:
        return jsonify({'error': 'Missing required field: url'}), 400
    
    # Set context (code_url and dataset_url optional)
    code_url = data.get('code_url')
    dataset_url = data.get('dataset_url')
    set_context(model_url, code_url, dataset_url)
    
    # Build tasks from metrics registry
    tasks = []
    for _, field, compute in registered():
        def _task(func=compute, model=model_url):
            def run():
                return func(model)
            return run
        tasks.append((field, _task()))
    
    # Run metrics in parallel
    t0 = time.perf_counter()
    results = run_parallel(tasks, timeout_s=90)
    net_latency_ms = int((time.perf_counter() - t0) * 1000)
    
    # Extract values and compute net score
    def _val(name: str) -> float:
        return float(results.get(name, {}).get('value', 0.0))
    
    scalars = {
        'ramp_up_time': _val('ramp_up_time'),
        'bus_factor': _val('bus_factor'),
        'license': _val('license'),
        'dataset_and_code_score': _val('dataset_and_code_score'),
        'dataset_quality': _val('dataset_quality'),
        'code_quality': _val('code_quality'),
        'performance_claims': _val('performance_claims'),
        'size_score': _val('size_score'),
    }
    
    net_score = combine(scalars)
    
    return jsonify({
        'net_score': net_score,
        'net_score_latency': net_latency_ms,
        'metrics': results
    }), 200