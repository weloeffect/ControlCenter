-- Reference KPI definitions. The Python service applies the same rules.

-- Acceptance rate: accepted / (accepted + refused). Timeouts are reported separately.
SELECT partner_id,
       AVG(CASE WHEN response_status = 'accepted' THEN 1.0 ELSE 0.0 END) AS acceptance_rate
FROM mission_offers
WHERE response_status IN ('accepted', 'refused')
GROUP BY partner_id;

-- Punctuality: arrival no later than 15 minutes after the appointment.
SELECT a.partner_id,
       AVG(CASE WHEN datetime(a.arrival_at) <= datetime(m.appointment_at, '+15 minutes') THEN 1.0 ELSE 0.0 END)
           AS punctuality_rate
FROM assignments a
JOIN missions m USING (mission_id)
WHERE a.status = 'completed'
GROUP BY a.partner_id;

-- Delivery time: mission completion to final delivery.
SELECT a.partner_id,
       AVG((julianday(m.delivered_at) - julianday(m.completed_at)) * 24.0) AS average_delivery_hours
FROM assignments a
JOIN missions m USING (mission_id)
WHERE a.status = 'completed' AND m.delivered_at IS NOT NULL
GROUP BY a.partner_id;

