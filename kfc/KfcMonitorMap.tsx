import { useEffect, useRef, useState } from 'react';
import AMapLoader from '@amap/amap-jsapi-loader';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { MapPinned, TriangleAlert } from 'lucide-react';
import {
  getStatusColor,
  getStatusLabel,
  type KfcDemoPoint,
} from '@/data/kfcDemoPoints';

declare global {
  interface Window {
    _AMapSecurityConfig?: {
      securityJsCode?: string;
    };
  }
}

interface KfcMonitorMapProps {
  points: KfcDemoPoint[];
  selectedPoint: KfcDemoPoint;
  onSelectPoint: (point: KfcDemoPoint) => void;
  selectedDate: string;
  dateOptions: Array<{ value: string; label: string }>;
  onDateChange: (date: string) => void;
}

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY || '0199c1c5a799561dadd5bd5f5936bc36';
const AMAP_SECURITY_JS_CODE =
  import.meta.env.VITE_AMAP_SECURITY_JS_CODE || 'be8eb411f4867194f90c19a588bb0fb8';

function buildMarkerHtml(point: KfcDemoPoint) {
  const color = getStatusColor(point.status);
  return `
    <div style="position: relative; transform: translate(-50%, -100%);">
      <div style="
        min-width: 44px;
        height: 44px;
        border-radius: 9999px;
        background: ${color};
        color: #fff;
        border: 3px solid rgba(255,255,255,0.95);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.22);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 14px;
        padding: 0 8px;
      ">${point.mentionRate}</div>
      <div style="
        position: absolute;
        left: 50%;
        bottom: -8px;
        transform: translateX(-50%);
        width: 0;
        height: 0;
        border-left: 8px solid transparent;
        border-right: 8px solid transparent;
        border-top: 10px solid ${color};
      "></div>
    </div>
  `;
}

function buildInfoHtml(point: KfcDemoPoint) {
  const color = getStatusColor(point.status);
  return `
    <div style="
      min-width: 240px;
      border-radius: 16px;
      overflow: hidden;
      background: #fff;
      box-shadow: 0 16px 40px rgba(15,23,42,0.18);
      font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    ">
      <div style="padding: 12px 14px; background: ${color}; color: #fff;">
        <div style="font-size: 14px; font-weight: 700;">${point.name}</div>
        <div style="font-size: 12px; opacity: 0.92; margin-top: 4px;">${point.pointType} · ${getStatusLabel(point.status)} · 提及率 ${point.mentionRate}%</div>
      </div>
      <div style="padding: 12px 14px; color: #0f172a; line-height: 1.6;">
        <div style="font-size: 12px; color: #475569;">${point.address}</div>
      </div>
    </div>
  `;
}

export default function KfcMonitorMap({
  points = [],
  selectedPoint,
  onSelectPoint,
  selectedDate,
  dateOptions = [],
  onDateChange,
}: KfcMonitorMapProps) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const infoWindowRef = useRef<any>(null);
  const [loadState, setLoadState] = useState<'idle' | 'ready' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let mounted = true;

    async function initMap() {
      if (!mapRef.current) return;

      try {
        window._AMapSecurityConfig = {
          securityJsCode: AMAP_SECURITY_JS_CODE,
        };

        const AMap = await AMapLoader.load({
          key: AMAP_KEY,
          version: '2.0',
          plugins: ['AMap.Scale', 'AMap.ToolBar'],
        });

        if (!mounted || !mapRef.current) {
          return;
        }

        const map = new AMap.Map(mapRef.current, {
          viewMode: '3D',
          zoom: 12,
          center: [121.4376, 31.1889],
          mapStyle: 'amap://styles/normal',
          resizeEnable: true,
        });

        map.addControl(new AMap.Scale());
        map.addControl(
          new AMap.ToolBar({
            position: 'RB',
          }),
        );

        const infoWindow = new AMap.InfoWindow({
          isCustom: true,
          offset: new AMap.Pixel(0, -18),
          closeWhenClickMap: true,
        });

        const markers = points.map((point) => {
          const marker = new AMap.Marker({
            position: [point.lng, point.lat],
            content: buildMarkerHtml(point),
            anchor: 'bottom-center',
            title: point.name,
          });
          marker.on('click', () => {
            onSelectPoint(point);
            infoWindow.setContent(buildInfoHtml(point));
            infoWindow.open(map, marker.getPosition());
          });
          return marker;
        });

        map.add(markers);
        map.setFitView(markers, false, [72, 72, 72, 72]);

        mapInstanceRef.current = map;
        markersRef.current = markers;
        infoWindowRef.current = infoWindow;
        setLoadState('ready');
      } catch (error) {
        console.error('AMap load failed', error);
        if (!mounted) return;
        setLoadState('error');
        setErrorMessage('高德地图加载失败，请检查网络或 Key 配置。');
      }
    }

    initMap();

    return () => {
      mounted = false;
      infoWindowRef.current?.close?.();
      markersRef.current = [];
      if (mapInstanceRef.current) {
        mapInstanceRef.current.destroy();
        mapInstanceRef.current = null;
      }
    };
  }, [onSelectPoint, points]);

  useEffect(() => {
    const map = mapInstanceRef.current;
    const infoWindow = infoWindowRef.current;
    if (!selectedPoint) {
      return;
    }
    const marker = markersRef.current.find((item) => item.getTitle?.() === selectedPoint.name);
    if (!map || !infoWindow || !marker) {
      return;
    }

    const position = marker.getPosition();
    map.setCenter(position);
    infoWindow.setContent(buildInfoHtml(selectedPoint));
    infoWindow.open(map, position);
  }, [selectedPoint]);

  return (
    <Card className="overflow-hidden border-gray-200 bg-white">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <MapPinned className="h-5 w-5 text-blue-600" />
              <CardTitle className="text-gray-800">监控点地图</CardTitle>
            </div>
            <CardDescription className="mt-2 text-gray-600">
              徐汇区 10 个监控点，支持点击查看监控点详情。
            </CardDescription>
          </div>

          <div className="w-full max-w-[220px] space-y-2">
            <Label htmlFor="kfc-map-date" className="text-sm font-medium text-gray-700">
              时间
            </Label>
            <Select value={selectedDate} onValueChange={onDateChange}>
              <SelectTrigger
                id="kfc-map-date"
                className="h-11 rounded-xl border-gray-300 bg-white text-gray-800"
              >
                <SelectValue placeholder="选择日期" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-300">
                {dateOptions.map((item) => (
                  <SelectItem
                    key={item.value}
                    value={item.value}
                    className="text-gray-800 focus:bg-blue-50 focus:text-blue-700"
                  >
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-3 text-xs">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            正常点位
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-amber-700">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            预警点位
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-rose-50 px-3 py-1 text-rose-700">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
            异常点位
          </div>
        </div>

        <div className="relative overflow-hidden rounded-2xl border border-gray-200 bg-slate-100">
          <div ref={mapRef} className="h-[340px] w-full md:h-[460px]" />

          {loadState === 'idle' && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-sm text-gray-600 backdrop-blur-sm">
              地图加载中...
            </div>
          )}

          {loadState === 'error' && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/90 p-6">
              <div className="max-w-sm rounded-2xl border border-rose-100 bg-white p-5 text-center shadow-sm">
                <TriangleAlert className="mx-auto mb-3 h-8 w-8 text-rose-500" />
                <div className="font-medium text-gray-900">地图暂时不可用</div>
                <p className="mt-2 text-sm text-gray-600">{errorMessage}</p>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
