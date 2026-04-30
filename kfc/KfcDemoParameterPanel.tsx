import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { metricDefinitions } from '@/lib/mockData';
import { kfcDemoKeywords, kfcDemoMetrics, kfcDemoPlatforms, kfcDemoProducts } from '@/data/kfcDemoFilters';
import { CalendarIcon, Settings } from 'lucide-react';
import { format } from 'date-fns';
import { zhCN } from 'date-fns/locale';

interface KfcDemoParameterValues {
  productId: string;
  keywordId: string;
  platformId: string;
  dateRange: {
    start: string;
    end: string;
  };
}

interface KfcDemoParameterPanelProps {
  values: KfcDemoParameterValues;
  onApply: (nextValues: KfcDemoParameterValues) => void;
  afterMetricContent?: ReactNode;
}

const DEMO_END_DATE = new Date('2026-03-12');

export default function KfcDemoParameterPanel({
  values,
  onApply,
  afterMetricContent,
}: KfcDemoParameterPanelProps) {
  const [selectedProduct, setSelectedProduct] = useState(values.productId);
  const [selectedKeyword, setSelectedKeyword] = useState(values.keywordId);
  const [selectedPlatform, setSelectedPlatform] = useState(values.platformId);
  const [startDate, setStartDate] = useState<Date | undefined>(new Date(values.dateRange.start));
  const [endDate, setEndDate] = useState<Date | undefined>(new Date(values.dateRange.end));

  useEffect(() => {
    setSelectedProduct(values.productId);
    setSelectedKeyword(values.keywordId);
    setSelectedPlatform(values.platformId);
    setStartDate(new Date(values.dateRange.start));
    setEndDate(new Date(values.dateRange.end));
  }, [values]);

  const filteredKeywords = useMemo(
    () => kfcDemoKeywords.filter((keyword) => keyword.productId === selectedProduct),
    [selectedProduct],
  );
  const selectedKeywordData = filteredKeywords.find((keyword) => keyword.id === selectedKeyword);
  const availablePlatforms = selectedKeywordData
    ? kfcDemoPlatforms.filter((platform) =>
        selectedKeywordData.platformIds.includes(platform.id),
      )
    : [];
  const availableMetrics = selectedKeywordData
    ? kfcDemoMetrics.filter((item) => selectedKeywordData.metricIds.includes(item.id))
    : [];
  const metric = availableMetrics[0] || null;
  const metricDescription = metric ? metricDefinitions[metric.id] || '' : '';

  useEffect(() => {
    if (!filteredKeywords.length) {
      return;
    }
    if (!filteredKeywords.some((keyword) => keyword.id === selectedKeyword)) {
      setSelectedKeyword(filteredKeywords[0].id);
    }
  }, [filteredKeywords, selectedKeyword]);

  useEffect(() => {
    if (!availablePlatforms.length) {
      return;
    }
    if (!availablePlatforms.some((platform) => platform.id === selectedPlatform)) {
      setSelectedPlatform(availablePlatforms[0].id);
    }
  }, [availablePlatforms, selectedPlatform]);

  const handleApply = () => {
    if (!startDate || !endDate) {
      return;
    }
    onApply({
      productId: selectedProduct,
      keywordId: selectedKeyword,
      platformId: selectedPlatform,
      dateRange: {
        start: format(startDate, 'yyyy-MM-dd'),
        end: format(endDate, 'yyyy-MM-dd'),
      },
    });
  };

  const handleQuickSelect = (days: number) => {
    const end = new Date(DEMO_END_DATE);
    const start = new Date(DEMO_END_DATE);
    start.setDate(start.getDate() - (days - 1));
    setStartDate(start);
    setEndDate(end);
    onApply({
      productId: selectedProduct,
      keywordId: selectedKeyword,
      platformId: selectedPlatform,
      dateRange: {
        start: format(start, 'yyyy-MM-dd'),
        end: format(end, 'yyyy-MM-dd'),
      },
    });
  };

  return (
    <Card className="bg-white border-gray-200">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-blue-600" />
          <CardTitle className="text-gray-800">参数设置</CardTitle>
        </div>
        <CardDescription className="text-gray-600">
          选择优化主体、关键词、平台和时间范围来查看数据
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="kfc-demo-product" className="text-gray-700">
              优化主体
            </Label>
            <Select
              value={selectedProduct}
              onValueChange={(value) => {
                setSelectedProduct(value);
                setSelectedKeyword('');
              }}
            >
              <SelectTrigger
                id="kfc-demo-product"
                className="bg-white border-gray-300 text-gray-800"
              >
                <SelectValue placeholder="选择优化主体" />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-300">
                {kfcDemoProducts.map((product) => (
                  <SelectItem
                    key={product.id}
                    value={product.id}
                    className="text-gray-800 focus:bg-blue-50 focus:text-blue-700"
                  >
                    {product.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="kfc-demo-keyword" className="text-gray-700">
              关键词
            </Label>
            <Select
              value={selectedKeyword}
              onValueChange={(value) => {
                setSelectedKeyword(value);
                setSelectedPlatform('');
              }}
            >
              <SelectTrigger
                id="kfc-demo-keyword"
                className="bg-white border-gray-300 text-gray-800"
              >
                <SelectValue placeholder={selectedProduct ? '选择关键词' : '请先选择优化主体'} />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-300">
                {filteredKeywords.map((keyword) => (
                  <SelectItem
                    key={keyword.id}
                    value={keyword.id}
                    className="text-gray-800 focus:bg-blue-50 focus:text-blue-700"
                  >
                    {keyword.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="kfc-demo-platform" className="text-gray-700">
              大模型平台
            </Label>
            <Select value={selectedPlatform} onValueChange={setSelectedPlatform}>
              <SelectTrigger
                id="kfc-demo-platform"
                className="bg-white border-gray-300 text-gray-800"
              >
                <SelectValue placeholder={selectedKeywordData ? '选择平台' : '请先选择关键词'} />
              </SelectTrigger>
              <SelectContent className="bg-white border-gray-300">
                {availablePlatforms.map((platform) => (
                  <SelectItem
                    key={platform.id}
                    value={platform.id}
                    className="text-gray-800 focus:bg-blue-50 focus:text-blue-700"
                  >
                    {platform.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {metric ? (
          <div className="space-y-2">
            <Label className="text-gray-700">监测指标（后端配置）</Label>
            <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="rounded bg-blue-600 px-3 py-1 text-sm font-medium text-white">
                    {metric.name}
                  </div>
                </div>
                <div className="text-sm font-medium text-gray-800">
                  基准线: {metric.threshold}%
                </div>
              </div>
              {metricDescription ? (
                <p className="mt-2 text-sm text-gray-700">{metricDescription}</p>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <Label className="text-gray-700">监测指标（后端配置）</Label>
            <div className="rounded-lg border border-dashed p-3 text-sm text-gray-500">
              暂无可用指标
            </div>
          </div>
        )}

        {afterMetricContent ? <div>{afterMetricContent}</div> : null}

        <div className="space-y-3">
          <Label className="text-gray-700">时间范围</Label>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleQuickSelect(7)}
              className="bg-white border-gray-300 text-gray-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300"
            >
              最近7天
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleQuickSelect(14)}
              className="bg-white border-gray-300 text-gray-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300"
            >
              最近14天
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleQuickSelect(30)}
              className="bg-white border-gray-300 text-gray-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300"
            >
              最近30天
            </Button>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label className="text-gray-700 text-sm">开始日期</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="w-full justify-start text-left font-normal bg-white border-gray-300 text-gray-800 hover:bg-gray-50 hover:text-gray-900"
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {startDate ? format(startDate, 'PPP', { locale: zhCN }) : '选择日期'}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0 bg-white border-gray-300">
                  <Calendar
                    mode="single"
                    selected={startDate}
                    onSelect={setStartDate}
                    initialFocus
                    className="text-gray-800"
                  />
                </PopoverContent>
              </Popover>
            </div>

            <div className="space-y-2">
              <Label className="text-gray-700 text-sm">结束日期</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className="w-full justify-start text-left font-normal bg-white border-gray-300 text-gray-800 hover:bg-gray-50 hover:text-gray-900"
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {endDate ? format(endDate, 'PPP', { locale: zhCN }) : '选择日期'}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0 bg-white border-gray-300">
                  <Calendar
                    mode="single"
                    selected={endDate}
                    onSelect={setEndDate}
                    initialFocus
                    className="text-gray-800"
                  />
                </PopoverContent>
              </Popover>
            </div>
          </div>
        </div>

        <Button
          onClick={handleApply}
          disabled={!selectedPlatform || !selectedKeyword}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
        >
          应用设置
        </Button>
      </CardContent>
    </Card>
  );
}
