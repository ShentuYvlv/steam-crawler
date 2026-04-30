import { useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { FileText } from 'lucide-react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { KfcDemoPoint } from '@/data/kfcDemoPoints';

interface KfcMentionRateDatum {
  date: string;
  label: string;
  mentionRate: number;
}

interface KfcQueryDetailChartProps {
  points: KfcDemoPoint[];
  selectedPoint: KfcDemoPoint;
  onSelectPoint: (point: KfcDemoPoint) => void;
  mentionRateSeries: KfcMentionRateDatum[];
  selectedDate: string;
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{
    color: string;
    name: string;
    value: number;
    payload: {
      date: string;
    };
  }>;
}

export default function KfcQueryDetailChart({
  points,
  selectedPoint,
  onSelectPoint,
  mentionRateSeries,
  selectedDate,
}: KfcQueryDetailChartProps) {
  useEffect(() => {
    if (!points.some((point) => point.id === selectedPoint.id) && points.length > 0) {
      onSelectPoint(points[0]);
    }
  }, [onSelectPoint, points, selectedPoint.id]);

  const currentMentionRate =
    mentionRateSeries.find((item) => item.date === selectedDate)?.mentionRate ??
    selectedPoint.mentionRate;

  const CustomTooltip = ({ active, payload }: TooltipProps) => {
    if (!active || !payload?.length) {
      return null;
    }

    return (
      <div className="rounded-xl border border-blue-200 bg-white p-3 shadow-lg">
        <div className="mb-2 text-sm font-medium text-gray-900">{payload[0].payload.date}</div>
        {payload.map((item) => (
          <div key={item.name} className="text-sm" style={{ color: item.color }}>
            {item.name}: {item.value}%
          </div>
        ))}
      </div>
    );
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader className="space-y-4">
        <div className="flex items-center gap-3">
          <FileText className="h-6 w-6 text-blue-600" />
          <div className="flex flex-wrap items-center gap-3 text-xl font-semibold tracking-tight text-gray-900 md:text-[2rem]">
            <CardTitle className="text-inherit">各监控点|跨时段优化表现</CardTitle>

          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 gap-4">
          <div className="space-y-2">
            <Label htmlFor="kfc-point-select" className="text-base font-medium text-gray-800">
              选择监控点
            </Label>
            <Select
              value={selectedPoint.id}
              onValueChange={(pointId) => {
                const point = points.find((item) => item.id === pointId);
                if (point) {
                  onSelectPoint(point);
                }
              }}
            >
              <SelectTrigger
                id="kfc-point-select"
                className="h-12 rounded-xl border-gray-300 bg-white text-gray-800"
              >
                <SelectValue placeholder="选择监控点" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-300 max-h-[320px]">
                {points.map((point) => (
                  <SelectItem
                    key={point.id}
                    value={point.id}
                    className="text-gray-800 focus:bg-blue-50 focus:text-blue-700"
                  >
                    {point.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-6">
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <div className="text-sm text-gray-500">监控点</div>
                <div className="mt-1 text-3xl font-semibold tracking-tight text-blue-700">
                  {selectedPoint.name}
                </div>
              </div>

              <div className="rounded-2xl border border-white/80 bg-white/80 px-5 py-4 shadow-sm">
                <div className="text-sm text-gray-500">当前日期提及率</div>
                <div className="mt-1 text-4xl font-bold tracking-tight text-gray-900">
                  {currentMentionRate}%
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-4 md:p-6">
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={mentionRateSeries} margin={{ top: 16, right: 24, left: 8, bottom: 12 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="#E5E7EB" />
              <XAxis dataKey="label" stroke="#6B7280" tick={{ fill: '#6B7280' }} />
              <YAxis domain={[0, 100]} stroke="#6B7280" tick={{ fill: '#6B7280' }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ color: '#6B7280' }} />
              <Line
                type="monotone"
                dataKey="mentionRate"
                name="提及率"
                stroke="#2563EB"
                strokeWidth={3}
                dot={{ fill: '#2563EB', r: 5 }}
                activeDot={{ r: 7, fill: '#2563EB' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
