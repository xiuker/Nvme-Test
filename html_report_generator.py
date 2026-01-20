import os
from typing import Dict, Optional
from datetime import datetime
from logger import ConsoleLogger


class HTMLReportGenerator:
    def __init__(self, logger: Optional[ConsoleLogger] = None):
        self.logger = logger

    def generate_report(self, analysis_result: Dict, output_path: str) -> bool:
        try:
            html_content = self._generate_html_content(analysis_result)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            if self.logger:
                self.logger.info(f'HTML报告生成成功: {output_path}')
            return True
        
        except Exception as e:
            if self.logger:
                self.logger.error(f'HTML报告生成失败: {e}')
            return False

    def _generate_html_content(self, analysis_result: Dict) -> str:
        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NVMe SSD测试报告 - {analysis_result["test_time"]}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}
        
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        
        .summary-card:hover {{
            transform: translateY(-5px);
        }}
        
        .summary-card h3 {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
        }}
        
        .summary-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }}
        
        .summary-card.pass .value {{
            color: #28a745;
        }}
        
        .summary-card.fail .value {{
            color: #dc3545;
        }}
        
        .summary-card.warning .value {{
            color: #ffc107;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section h2 {{
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        .ssd-card {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s;
        }}
        
        .ssd-card:hover {{
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        }}
        
        .ssd-card.status-pass {{
            border-color: #28a745;
            background: linear-gradient(to right, #d4edda, white);
        }}
        
        .ssd-card.status-fail {{
            border-color: #dc3545;
            background: linear-gradient(to right, #f8d7da, white);
        }}
        
        .ssd-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .ssd-title {{
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }}
        
        .ssd-status {{
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        
        .ssd-status.pass {{
            background: #28a745;
            color: white;
        }}
        
        .ssd-status.fail {{
            background: #dc3545;
            color: white;
        }}
        
        .ssd-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .info-item {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
        }}
        
        .info-item label {{
            display: block;
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }}
        
        .info-item .value {{
            color: #333;
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        .error-list, .warning-list {{
            margin-top: 15px;
        }}
        
        .error-item {{
            background: #f8d7da;
            border-left: 4px solid #dc3545;
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 5px;
        }}
        
        .warning-item {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 5px;
        }}
        
        .error-type {{
            font-weight: bold;
            color: #dc3545;
            margin-bottom: 5px;
        }}
        
        .warning-type {{
            font-weight: bold;
            color: #856404;
            margin-bottom: 5px;
        }}
        
        .temperature-chart {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-top: 15px;
        }}
        
        .temperature-chart h4 {{
            color: #333;
            margin-bottom: 15px;
        }}
        
        .temp-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            text-align: center;
        }}
        
        .temp-stat {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .temp-stat .label {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }}
        
        .temp-stat .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .test-items {{
            margin-top: 15px;
        }}
        
        .test-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }}
        
        .test-item-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .test-item-name {{
            font-weight: bold;
            color: #333;
            font-size: 1.1em;
        }}
        
        .test-item-status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.9em;
            font-weight: bold;
        }}
        
        .test-item-status.pass {{
            background: #28a745;
            color: white;
        }}
        
        .test-item-status.fail {{
            background: #dc3545;
            color: white;
        }}
        
        .test-item-details {{
            color: #666;
            font-size: 0.9em;
            line-height: 1.6;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            color: #666;
            border-top: 1px solid #e0e0e0;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }}
        
        .progress-fill.pass {{
            background: #28a745;
        }}
        
        .progress-fill.fail {{
            background: #dc3545;
        }}
        
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>NVMe SSD测试报告</h1>
            <p>测试时间: {analysis_result["test_time"]}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card pass">
                <h3>总体状态</h3>
                <div class="value">{analysis_result["overall_status"]}</div>
            </div>
            <div class="summary-card">
                <h3>测试SSD数量</h3>
                <div class="value">{len(analysis_result["ssd_results"])}</div>
            </div>
            <div class="summary-card pass">
                <h3>通过数量</h3>
                <div class="value">{sum(1 for ssd in analysis_result["ssd_results"].values() if ssd["status"] == "PASS")}</div>
            </div>
            <div class="summary-card fail">
                <h3>失败数量</h3>
                <div class="value">{sum(1 for ssd in analysis_result["ssd_results"].values() if ssd["status"] == "FAIL")}</div>
            </div>
            <div class="summary-card fail">
                <h3>错误数量</h3>
                <div class="value">{analysis_result["error_count"]}</div>
            </div>
            <div class="summary-card warning">
                <h3>警告数量</h3>
                <div class="value">{analysis_result["warning_count"]}</div>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>测试结果详情</h2>
'''

        for ssd_sn, ssd_result in analysis_result["ssd_results"].items():
            status_class = "pass" if ssd_result["status"] == "PASS" else "fail"
            status_text = "PASS" if ssd_result["status"] == "PASS" else "FAIL"
            
            html += f'''
                <div class="ssd-card status-{status_class}">
                    <div class="ssd-header">
                        <div class="ssd-title">SSD SN: {ssd_sn}</div>
                        <div class="ssd-status {status_class}">{status_text}</div>
                    </div>
                    
                    <div class="ssd-info">
                        <div class="info-item">
                            <label>错误数量</label>
                            <div class="value">{ssd_result["error_count"]}</div>
                        </div>
                        <div class="info-item">
                            <label>警告数量</label>
                            <div class="value">{ssd_result["warning_count"]}</div>
                        </div>
                        <div class="info-item">
                            <label>测试项目数</label>
                            <div class="value">{len(ssd_result["test_items"])}</div>
                        </div>
                    </div>
'''
            
            if ssd_result["errors"]:
                html += '''
                    <div class="error-list">
                        <h3>错误列表</h3>
'''
                for error in ssd_result["errors"]:
                    html += f'''
                        <div class="error-item">
                            <div class="error-type">[{error["type"]}]</div>
                            <div>{error["message"]}</div>
                            <div style="font-size: 0.9em; color: #666; margin-top: 5px;">时间: {error.get("timestamp", "未知")}</div>
                        </div>
'''
                html += '''
                    </div>
'''
            
            if ssd_result["warnings"]:
                html += '''
                    <div class="warning-list">
                        <h3>警告列表</h3>
'''
                for warning in ssd_result["warnings"]:
                    html += f'''
                        <div class="warning-item">
                            <div class="warning-type">警告</div>
                            <div>{warning}</div>
                        </div>
'''
                html += '''
                    </div>
'''
            
            if "temperature_analysis" in ssd_result:
                temp = ssd_result["temperature_analysis"]
                html += f'''
                    <div class="temperature-chart">
                        <h4>温度分析</h4>
                        <div class="temp-stats">
                            <div class="temp-stat">
                                <div class="label">最高温度</div>
                                <div class="value">{temp["max_temp"]}°C</div>
                            </div>
                            <div class="temp-stat">
                                <div class="label">最低温度</div>
                                <div class="value">{temp["min_temp"]}°C</div>
                            </div>
                            <div class="temp-stat">
                                <div class="label">平均温度</div>
                                <div class="value">{temp["avg_temp"]:.1f}°C</div>
                            </div>
                        </div>
                    </div>
'''
            
            if ssd_result["test_items"]:
                html += '''
                    <div class="test-items">
                        <h3>测试项目详情</h3>
'''
                for test_item_name, test_item_result in ssd_result["test_items"].items():
                    item_status_class = "pass" if test_item_result["status"] == "PASS" else "fail"
                    item_status_text = "PASS" if test_item_result["status"] == "PASS" else "FAIL"
                    
                    html += f'''
                        <div class="test-item">
                            <div class="test-item-header">
                                <div class="test-item-name">{test_item_name}</div>
                                <div class="test-item-status {item_status_class}">{item_status_text}</div>
                            </div>
                            <div class="test-item-details">
'''
                    if "cycle" in test_item_result:
                        html += f'<div>测试轮次: {test_item_result["cycle"]}</div>'
                    if "iops" in test_item_result:
                        html += f'<div>IOPS: {test_item_result["iops"]}</div>'
                    if "bandwidth" in test_item_result:
                        html += f'<div>带宽: {test_item_result["bandwidth"]}</div>'
                    if "latency" in test_item_result:
                        html += f'<div>延迟: {test_item_result["latency"]}</div>'
                    
                    html += '''
                            </div>
                        </div>
'''
                html += '''
                    </div>
'''
            
            html += '''
                </div>
'''
        
        html += f'''
            </div>
        </div>
        
        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>NVMe SSD测试系统 v1.0</p>
        </div>
    </div>
</body>
</html>
'''
        return html
