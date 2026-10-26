import request from "../pipeline/request";
import { requireBusinessId } from "@/utils/portal/businessId";

// 查询AI模型列表
export function listModel(query) {
  return request({
    url: "/ai/model/list",
    method: "get",
    params: query,
  });
}

// 查询所有AI模型列表
export function listModelAll() {
  return request({
    url: "/ai/model/all",
    method: "get",
  });
}

// 查询AI模型详细
export function getModel(modelId) {
  return request({
    url: "/ai/model/" + requireBusinessId(modelId),
    method: "get",
  });
}

// 新增AI模型
export function addModel(data) {
  return request({
    url: "/ai/model",
    method: "post",
    data: data,
  });
}

// 修改AI模型
export function updateModel(data) {
  return request({
    url: "/ai/model",
    method: "put",
    data: data,
  });
}

// 删除AI模型
export function delModel(modelId) {
  return request({
    url: "/ai/model/" + requireBusinessId(modelId),
    method: "delete",
  });
}

// 测试AI模型连通性
export function testModel(modelId) {
  return request({
    url: "/ai/model/" + requireBusinessId(modelId) + "/test",
    method: "post",
  });
}
