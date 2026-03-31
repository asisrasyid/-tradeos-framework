# PATTERN & THEORY TEMPLATE — TradeOS v5.1
## HMM State Sequence Pattern
{"code":"BnR_BULL_S0S3S4","pattern_type":"state_sequence","state_sequence":{"seq":[0,3,4],"label":"S0S3S4","min_log_prob":-6.0}}
## Theory
{"name":"B&R Bullish XAUUSD H1","instrument":"XAUUSD","direction":"LONG","threshold":12,"min_confidence":62.0}
## HMM Factor (+5 dp)
{"factor_code":"HMM_STATE_SEQ_MATCH","factor_type":"state_sequence_match","decision_point":5}
## Veto Factor (-4 dp)
{"factor_code":"HMM_STATE_IS_RANGING","factor_type":"c_code_condition","decision_point":-4}
