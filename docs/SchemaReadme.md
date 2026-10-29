可以，下面这个可以作为你项目里的**标准结构化输出模板**。

```json
{
  "routing": {
    "need_record": false,
    "need_advice": false,
    "need_plan": false,
    "need_reminder": false,
    "need_history": false
  },
  "confidence": {
    "need_record": 0.0,
    "need_advice": 0.0,
    "need_plan": 0.0,
    "need_reminder": 0.0,
    "need_history": 0.0
  },
  "slots": {
    "record": {
      "blood_pressure": null,
      "blood_glucose": null,
      "weight": null,
      "diet": null,
      "exercise": null,
      "medication": null,
      "symptom": null
    },
    "advice": {
      "topic": null,
      "question": null,
      "related_metrics": []
    },
    "plan": {
      "goal": null,
      "duration": null,
      "preferences": [],
      "constraints": []
    },
    "reminder": {
      "action": null,
      "task": null,
      "time": null,
      "repeat": null
    },
    "history": {
      "metric": null,
      "time_range": null,
      "aggregation": null
    }
  },
  "missing_fields": [],
  "risk_flags": [],
  "normalized": {
    "date": null,
    "time_of_day": null,
    "units": {}
  }
}
```

具体字段展开模板：

```json
{
  "blood_pressure": {
    "systolic": null,
    "diastolic": null,
    "unit": "mmHg",
    "time": null
  },
  "blood_glucose": {
    "value": null,
    "unit": "mmol/L",
    "type": null,
    "time": null
  },
  "weight": {
    "value": null,
    "unit": "kg",
    "time": null
  },
  "diet": {
    "meal": null,
    "content": null,
    "time": null
  },
  "exercise": {
    "type": null,
    "duration_minutes": null,
    "time": null
  },
  "medication": {
    "name": null,
    "dose": null,
    "time": null
  },
  "symptom": {
    "name": null,
    "duration": null,
    "severity": null,
    "time": null
  }
}
```

一个完整示例：

```json
{
  "routing": {
    "need_record": true,
    "need_advice": true,
    "need_plan": false,
    "need_reminder": true,
    "need_history": false
  },
  "confidence": {
    "need_record": 0.96,
    "need_advice": 0.9,
    "need_plan": 0.08,
    "need_reminder": 0.94,
    "need_history": 0.12
  },
  "slots": {
    "record": {
      "blood_pressure": {
        "systolic": 145,
        "diastolic": 92,
        "unit": "mmHg",
        "time": "今天早上"
      },
      "blood_glucose": null,
      "weight": null,
      "diet": null,
      "exercise": null,
      "medication": null,
      "symptom": null
    },
    "advice": {
      "topic": "blood_pressure",
      "question": "血压是否偏高",
      "related_metrics": ["blood_pressure"]
    },
    "plan": {
      "goal": null,
      "duration": null,
      "preferences": [],
      "constraints": []
    },
    "reminder": {
      "action": "create",
      "task": "测血压",
      "time": "明早",
      "repeat": null
    },
    "history": {
      "metric": null,
      "time_range": null,
      "aggregation": null
    }
  },
  "missing_fields": [],
  "risk_flags": [],
  "normalized": {
    "date": null,
    "time_of_day": "morning",
    "units": {
      "blood_pressure": "mmHg"
    }
  }
}
```
